"""
python API module for Cobbler
see source for cobbler.py, or pydoc, for example usage.
CLI apps and daemons should import api.py, and no other cobbler code.

Copyright 2006-2008, Red Hat, Inc
Michael DeHaan <mdehaan@redhat.com>

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
02110-1301  USA
"""

import yaml
import config
import utils
import action_sync
import action_check
import action_deploy
import action_import
import action_reposync
import action_status
import action_validate
import action_buildiso
import action_replicate
import action_acl
import action_report
import action_power
import action_hardlink
from cexceptions import *
import sub_process
import module_loader
import kickgen
import yumgen
import pxegen
import acls
from utils import _

import logging
import time
import random
import os
import xmlrpclib
import traceback

ERROR = 100
INFO  = 10
DEBUG = 5

# notes on locking:
# BootAPI is a singleton object
# the XMLRPC variants allow 1 simultaneous request
# therefore we flock on /etc/cobbler/settings for now
# on a request by request basis.

class BootAPI:

    __shared_state = {}
    __has_loaded = False

    def __init__(self, log_settings={}, is_cobblerd=False):
        """
        Constructor
        """

        self.__dict__ = BootAPI.__shared_state
        self.log_settings = log_settings
        self.perms_ok = False
        if not BootAPI.__has_loaded:

            # NOTE: we do not log all API actions, because
            # a simple CLI invocation may call adds and such
            # to load the config, which would just fill up
            # the logs, so we'll do that logging at CLI
            # level (and remote.py web service level) instead.

            random.seed()
            self.is_cobblerd = is_cobblerd

            try:
                self.logger = self.__setup_logger("api")
            except CX:
                # return to CLI/other but perms are not valid
                # perms_ok is False
                return

            # FIMXE: conslidate into 1 server instance

            self.selinux_enabled = utils.is_selinux_enabled()
            self.dist = utils.check_dist()
            self.os_version = utils.os_release()

            self.acl_engine = acls.AclEngine()
            
            BootAPI.__has_loaded   = True

            module_loader.load_modules()

            self._config         = config.Config(self)
            self.deserialize()

            self.authn = self.get_module_from_file(
                "authentication",
                "module",
                "authn_configfile"
            )
            self.authz  = self.get_module_from_file(
                "authorization",
                "module",
                "authz_allowall"
            )
            self.kickgen = kickgen.KickGen(self._config)
            self.yumgen  = yumgen.YumGen(self._config)
            self.pxegen  = pxegen.PXEGen(self._config)
            self.logger.debug("API handle initialized")
            self.perms_ok = True


    def __setup_logger(self,name):
        return utils.setup_logger(name, is_cobblerd=self.is_cobblerd, **self.log_settings)
    
    def is_selinux_enabled(self):
        """
        Returns whether selinux is enabled on the cobbler server.
        We check this just once at cobbler API init time, because
        a restart is required to change this; this does /not/ check
        enforce/permissive, nor does it need to.
        """
        return self.selinux_enabled

    def is_selinux_supported(self):
        """
        Returns whether or not the OS is sufficient enough
        to run with SELinux enabled (currently EL 5 or later).
        """
        self.dist
        if self.dist == "redhat" and self.os_version < 5:
           # doesn't support public_content_t
           return False 
        return True

    def _internal_cache_update(self, collection_type, name, remove=False):
        """
        Update cobblerd so it won't have to ever reload the config, once started.
        """
        # FIXME: take value from settings, use raw port
        if self.is_cobblerd:
           # don't signal yourself, that's asking for trouble.
           return True
        self.server = xmlrpclib.Server("http://127.0.0.1:%s" % self.settings().xmlrpc_port)
        try:
            if not remove:
                self.server.internal_cache_update(collection_type, name)
            else:
                self.server.internal_cache_remove(collection_type, name)
        except Exception, e:
            if len(e.args) == 2 and e[0] == 111:
                # if cobblerd is not running, no harm done, nothing to signal
                pass
            else: 
                raise
        return False

    def last_modified_time(self):
        """
        Returns the time of the last modification to cobbler, made by any
        API instance, regardless of the serializer type.
        """
        if not os.path.exists("/var/lib/cobbler/.mtime"):
            fd = open("/var/lib/cobbler/.mtime","w")
            fd.write("0")
            fd.close()
            return 0
        fd = open("/var/lib/cobbler/.mtime")
        data = fd.read().strip()
        return float(data)

    def log(self,msg,args=None,debug=False):
        if debug:
            logger = self.logger.debug
        else:
            logger = self.logger.info 
        if args is None:
            logger("%s" % msg)
        else:
            logger("%s; %s" % (msg, str(args)))

    def version(self, extended=False):
        """
        What version is cobbler?

        If extended == False, returns a float for backwards compatibility
         
        If extended == True, returns a dict:

            gitstamp      -- the last git commit hash
            gitdate       -- the last git commit date on the builder machine
            builddate     -- the time of the build
            version       -- something like "1.3.2"
            version_tuple -- something like [ 1, 3, 2 ]
        """
        fd = open("/var/lib/cobbler/version")
        ydata = fd.read()
        fd.close()
        data = yaml.load(ydata)
        if not extended:
            # for backwards compatibility and use with koan's comparisons
            elems = data["version_tuple"] 
            return int(elems[0]) + 0.1*int(elems[1]) + 0.001*int(elems[2])
        else:
            return data

    def clear(self):
        """
        Forget about current list of profiles, distros, and systems
        """
        return self._config.clear()

    def __cmp(self,a,b):
        return cmp(a.name,b.name)

    def systems(self):
        """
        Return the current list of systems
        """
        return self._config.systems()

    def profiles(self):
        """
        Return the current list of profiles
        """
        return self._config.profiles()

    def distros(self):
        """
        Return the current list of distributions
        """
        return self._config.distros()

    def repos(self):
        """
        Return the current list of repos
        """
        return self._config.repos()

    def images(self):
        """
        Return the current list of images
        """
        return self._config.images()

    def networks(self):
        """
        Return the current list of networks
        """
        return self._config.networks()

    def settings(self):
        """
        Return the application configuration
        """
        return self._config.settings()

    def update(self):
        """
        This can be called is no longer used by cobbler.
        And is here to just avoid breaking older scripts.
        """
        return True

    def copy_distro(self, ref, newname):
        self.log("copy_distro",[ref.name, newname])
        return self._config.distros().copy(ref,newname)

    def copy_profile(self, ref, newname):
        self.log("copy_profile",[ref.name, newname])
        return self._config.profiles().copy(ref,newname)

    def copy_system(self, ref, newname):
        self.log("copy_system",[ref.name, newname])
        return self._config.systems().copy(ref,newname)

    def copy_repo(self, ref, newname):
        self.log("copy_repo",[ref.name, newname])
        return self._config.repos().copy(ref,newname)
    
    def copy_image(self, ref, newname):
        self.log("copy_image",[ref.name, newname])
        return self._config.images().copy(ref,newname)

    def copy_network(self, ref, newname):
        self.log("copy_network",[ref.name, newname])
        return self._config.networks().copy(ref,newname)

    def remove_distro(self, ref, recursive=False, delete=True, with_triggers=True, ):
        if type(ref) != str:
           self.log("remove_distro",[ref.name])
           return self._config.distros().remove(ref.name, recursive=recursive, with_delete=delete, with_triggers=with_triggers)
        else:
           self.log("remove_distro",ref)
           return self._config.distros().remove(ref, recursive=recursive, with_delete=delete, with_triggers=with_triggers)

    def remove_profile(self,ref, recursive=False, delete=True, with_triggers=True):
        if type(ref) != str:
           self.log("remove_profile",[ref.name])
           return self._config.profiles().remove(ref.name, recursive=recursive, with_delete=delete, with_triggers=with_triggers) 
        else:
           self.log("remove_profile",ref)
           return self._config.profiles().remove(ref, recursive=recursive, with_delete=delete, with_triggers=with_triggers)

    def remove_system(self, ref, recursive=False, delete=True, with_triggers=True):
        if type(ref) != str:
           self.log("remove_system",[ref.name])
           return self._config.systems().remove(ref.name, with_delete=delete, with_triggers=with_triggers)
        else:
           self.log("remove_system",ref)
           return self._config.systems().remove(ref, with_delete=delete, with_triggers=with_triggers)

    def remove_repo(self, ref, recursive=False, delete=True, with_triggers=True):
        if type(ref) != str:
           self.log("remove_repo",[ref.name])
           return self._config.repos().remove(ref.name, with_delete=delete, with_triggers=with_triggers)
        else:    
           self.log("remove_repo",ref)
           return self._config.repos().remove(ref, with_delete=delete, with_triggers=with_triggers)

    def remove_image(self, ref, recursive=False, delete=True, with_triggers=True):
        if type(ref) != str:
           self.log("remove_image",[ref.name])
           return self._config.images().remove(ref.name, recursive=recursive, with_delete=delete, with_triggers=with_triggers)
        else:
           self.log("remove_image",ref)
           return self._config.images().remove(ref, recursive=recursive, with_delete=delete, with_triggers=with_triggers)

    def remove_network(self, ref, recursive=False, delete=True, with_triggers=True):
        if type(ref) != str:
           self.log("remove_network",[ref.name])
           return self._config.networks().remove(ref.name, recursive=recursive, with_delete=delete, with_triggers=with_triggers)
        else:
           self.log("remove_image",ref)
           return self._config.networks().remove(ref, recursive=recursive, with_delete=delete, with_triggers=with_triggers)

    def rename_distro(self, ref, newname):
        self.log("rename_distro",[ref.name,newname])
        return self._config.distros().rename(ref,newname)

    def rename_profile(self, ref, newname):
        self.log("rename_profiles",[ref.name,newname])
        return self._config.profiles().rename(ref,newname)

    def rename_system(self, ref, newname):
        self.log("rename_system",[ref.name,newname])
        return self._config.systems().rename(ref,newname)

    def rename_repo(self, ref, newname):
        self.log("rename_repo",[ref.name,newname])
        return self._config.repos().rename(ref,newname)
    
    def rename_image(self, ref, newname):
        self.log("rename_image",[ref.name,newname])
        return self._config.images().rename(ref,newname)

    def rename_network(self, ref, newname):
        self.log("rename_network",[ref.name,newname])
        return self._config.networks().rename(ref,newname)

    def new_distro(self,is_subobject=False):
        self.log("new_distro",[is_subobject])
        return self._config.new_distro(is_subobject=is_subobject)

    def new_profile(self,is_subobject=False):
        self.log("new_profile",[is_subobject])
        return self._config.new_profile(is_subobject=is_subobject)
    
    def new_system(self,is_subobject=False):
        self.log("new_system",[is_subobject])
        return self._config.new_system(is_subobject=is_subobject)

    def new_repo(self,is_subobject=False):
        self.log("new_repo",[is_subobject])
        return self._config.new_repo(is_subobject=is_subobject)
    
    def new_image(self,is_subobject=False):
        self.log("new_image",[is_subobject])
        return self._config.new_image(is_subobject=is_subobject)

    def new_network(self,is_subobject=False):
        self.log("new_network",[is_subobject])
        return self._config.new_network(is_subobject=is_subobject)

    def add_distro(self, ref, check_for_duplicate_names=False, save=True):
        self.log("add_distro",[ref.name])
        rc = self._config.distros().add(ref,check_for_duplicate_names=check_for_duplicate_names,save=save)
        return rc

    def add_profile(self, ref, check_for_duplicate_names=False,save=True):
        self.log("add_profile",[ref.name])
        rc = self._config.profiles().add(ref,check_for_duplicate_names=check_for_duplicate_names,save=save)
        return rc

    def add_system(self, ref, check_for_duplicate_names=False, check_for_duplicate_netinfo=False, save=True):
        self.log("add_system",[ref.name])
        rc = self._config.systems().add(ref,check_for_duplicate_names=check_for_duplicate_names,check_for_duplicate_netinfo=check_for_duplicate_netinfo,save=save)
        return rc

    def add_repo(self, ref, check_for_duplicate_names=False,save=True):
        self.log("add_repo",[ref.name])
        rc = self._config.repos().add(ref,check_for_duplicate_names=check_for_duplicate_names,save=save)
        return rc

    def add_image(self, ref, check_for_duplicate_names=False,save=True):
        self.log("add_image",[ref.name])
        rc = self._config.images().add(ref,check_for_duplicate_names=check_for_duplicate_names,save=save)
        return rc

    def add_network(self, ref, check_for_duplicate_names=False,save=True):
        self.log("add_network",[ref.name])
        rc = self._config.networks().add(ref,check_for_duplicate_names=check_for_duplicate_names,save=save)
        return rc

    def find_distro(self, name=None, return_list=False, no_errors=False, **kargs):
        return self._config.distros().find(name=name, return_list=return_list, no_errors=no_errors, **kargs)
        
    def find_profile(self, name=None, return_list=False, no_errors=False, **kargs):
        return self._config.profiles().find(name=name, return_list=return_list, no_errors=no_errors, **kargs)

    def find_system(self, name=None, return_list=False, no_errors=False, **kargs):
        return self._config.systems().find(name=name, return_list=return_list, no_errors=no_errors, **kargs)

    def find_repo(self, name=None, return_list=False, no_errors=False, **kargs):
        return self._config.repos().find(name=name, return_list=return_list, no_errors=no_errors, **kargs)

    def find_image(self, name=None, return_list=False, no_errors=False, **kargs):
        return self._config.images().find(name=name, return_list=return_list, no_errors=no_errors, **kargs)

    def find_network(self, name=None, return_list=False, no_errors=False, **kargs):
        return self._config.networks().find(name=name, return_list=return_list, no_errors=no_errors, **kargs)

    def __since(self,mtime,collector,collapse=False):
        """
        Called by get_*_since functions.
        """
        results1 = collector()
        results2 = []
        for x in results1:
           if x.mtime == 0 or x.mtime >= mtime:
              if not collapse:
                  results2.append(x)
              else:
                  results2.append(x.to_datastruct_with_cache())
        return results2

    def get_distros_since(self,mtime,collapse=False):
        """
        Returns distros modified since a certain time (in seconds since Epoch)
        collapse=True specifies returning a hash instead of objects.
        """
        return self.__since(mtime,self.distros,collapse=collapse)

    def get_profiles_since(self,mtime,collapse=False):
        return self.__since(mtime,self.profiles,collapse=collapse)

    def get_systems_since(self,mtime,collapse=False):
        return self.__since(mtime,self.systems,collapse=collapse)

    def get_repos_since(self,mtime,collapse=False):
        return self.__since(mtime,self.repos,collapse=collapse)

    def get_images_since(self,mtime,collapse=False):
        return self.__since(mtime,self.images,collapse=collapse)

    def get_networks_since(self,mtime,collapse=False):
        return self.__since(mtime,self.networks,collapse=collapse)


    def dump_vars(self, obj, format=False):
        return obj.dump_vars(format)

    def auto_add_repos(self):
        """
        Import any repos this server knows about and mirror them.
        Credit: Seth Vidal.
        """
        self.log("auto_add_repos")
        try:
            import yum
        except:
            raise CX(_("yum is not installed"))

        version = yum.__version__
        (a,b,c) = version.split(".")
        version = a* 1000 + b*100 + c
        if version < 324:
            raise CX(_("need yum > 3.2.4 to proceed"))

        base = yum.YumBase()
        base.doRepoSetup()
        repos = base.repos.listEnabled()
        if len(repos) == 0:
            raise CX(_("no repos enabled/available -- giving up."))

        for repo in repos:
            url = repo.urls[0]
            cobbler_repo = self.new_repo()
            auto_name = repo.name.replace(" ","")
            # FIXME: probably doesn't work for yum-rhn-plugin ATM
            cobbler_repo.set_mirror(url)
            cobbler_repo.set_name(auto_name)
            print "auto adding: %s (%s)" % (auto_name, url)
            self._config.repos().add(cobbler_repo,save=True)

        # run cobbler reposync to apply changes
        return True 

    def get_repo_config_for_profile(self,obj):
        return self.yumgen.get_yum_config(obj,True)
    
    def get_repo_config_for_system(self,obj):
        return self.yumgen.get_yum_config(obj,False)

    def get_template_file_for_profile(self,obj,path):
        template_results = self.pxegen.write_templates(obj,False,path)
        if template_results.has_key(path):
            return template_results[path]
        else:
            return "# template path not found for specified profile"

    def get_template_file_for_system(self,obj,path):
        template_results = self.pxegen.write_templates(obj,False,path)
        if template_results.has_key(path):
            return template_results[path]
        else:
            return "# template path not found for specified system"

    def generate_kickstart(self,profile,system):
        self.log("generate_kickstart")
        if system:
            return self.kickgen.generate_kickstart_for_system(system)
        else:
            return self.kickgen.generate_kickstart_for_profile(profile) 

    def check(self):
        """
        See if all preqs for network booting are valid.  This returns
        a list of strings containing instructions on things to correct.
        An empty list means there is nothing to correct, but that still
        doesn't mean there are configuration errors.  This is mainly useful
        for human admins, who may, for instance, forget to properly set up
        their TFTP servers for PXE, etc.
        """
        self.log("check")
        check = action_check.BootCheck(self._config)
        return check.run()

    def validateks(self):
        """
        Use ksvalidator (from pykickstart, if available) to determine
        whether the cobbler kickstarts are going to be (likely) well
        accepted by Anaconda.  Presence of an error does not indicate
        the kickstart is bad, only that the possibility exists.  ksvalidator
        is not available on all platforms and can not detect "future"
        kickstart format correctness.
        """
        self.log("validateks")
        validator = action_validate.Validate(self._config)
        return validator.run()

    def sync(self,verbose=False):
        """
        Take the values currently written to the configuration files in
        /etc, and /var, and build out the information tree found in
        /tftpboot.  Any operations done in the API that have not been
        saved with serialize() will NOT be synchronized with this command.
        """
        self.log("sync")
        sync = self.get_sync(verbose=verbose)
        return sync.run()

    def get_sync(self,verbose=False):
        self.dhcp = self.get_module_from_file(
           "dhcp",
           "module",
           "manage_isc"
        ).get_manager(self._config)
        self.dns = self.get_module_from_file(
           "dns",
           "module",
           "manage_bind"
        ).get_manager(self._config)
        return action_sync.BootSync(self._config,dhcp=self.dhcp,dns=self.dns,verbose=verbose)

    def reposync(self, name=None, tries=1, nofail=False):
        """
        Take the contents of /var/lib/cobbler/repos and update them --
        or create the initial copy if no contents exist yet.
        """
        self.log("reposync",[name])
        reposync = action_reposync.RepoSync(self._config, tries=tries, nofail=nofail)
        return reposync.run(name)

    def status(self,mode=None):
        self.log("status")
        statusifier = action_status.BootStatusReport(self._config,mode)
        return statusifier.run()

    def import_tree(self,mirror_url,mirror_name,network_root=None,kickstart_file=None,rsync_flags=None,arch=None,breed=None,os_version=None):
        """
        Automatically import a directory tree full of distribution files.
        mirror_url can be a string that represents a path, a user@host 
        syntax for SSH, or an rsync:// address.  If mirror_url is a 
        filesystem path and mirroring is not desired, set network_root 
        to something like "nfs://path/to/mirror_url/root" 
        """
        self.log("import_tree",[mirror_url, mirror_name, network_root, kickstart_file, rsync_flags])
        importer = action_import.Importer(
            self, self._config, mirror_url, mirror_name, network_root, kickstart_file, rsync_flags, arch, breed, os_version
        )
        return importer.run()

    def acl_config(self,adduser=None,addgroup=None,removeuser=None,removegroup=None):
        """
        Configures users/groups to run the cobbler CLI as non-root.
        Pass in only one option at a time.  Powers "cobbler aclconfig"
        """
        acl = action_acl.AclConfig(self._config)
        return acl.run(
            adduser=adduser,
            addgroup=addgroup,
            removeuser=removeuser,
            removegroup=removegroup
        )

    def serialize(self):
        """
        Save the config file(s) to disk.
        """
        self.log("serialize")
        return self._config.serialize()

    def deserialize(self):
        """
        Load the current configuration from config file(s)
        Cobbler internal use only.
        """
        return self._config.deserialize()

    def deserialize_raw(self,collection_name):
        """
        Get the collection back just as raw data.
        Cobbler internal use only.
        """
        return self._config.deserialize_raw(collection_name)

    def deserialize_item_raw(self,collection_name,obj_name):
        """
        Get an object back as raw data.
        Can be very fast for shelve or catalog serializers
        Cobbler internal use only.
        """
        return self._config.deserialize_item_raw(collection_name,obj_name)

    def get_module_by_name(self,module_name):
        """
        Returns a loaded cobbler module named 'name', if one exists, else None.
        Cobbler internal use only.
        """
        return module_loader.get_module_by_name(module_name)

    def get_module_from_file(self,section,name,fallback=None):
        """
        Looks in /etc/cobbler/modules.conf for a section called 'section'
        and a key called 'name', and then returns the module that corresponds
        to the value of that key.
        Cobbler internal use only.
        """
        return module_loader.get_module_from_file(section,name,fallback)

    def get_modules_in_category(self,category):
        """
        Returns all modules in a given category, for instance "serializer", or "cli".
        Cobbler internal use only.
        """
        return module_loader.get_modules_in_category(category)

    def authenticate(self,user,password):
        """
        (Remote) access control.
        Cobbler internal use only.
        """
        rc = self.authn.authenticate(self,user,password)
        self.log("authenticate",[user,rc])
        return rc 

    def authorize(self,user,resource,arg1=None,arg2=None):
        """
        (Remote) access control.
        Cobbler internal use only.
        """
        rc = self.authz.authorize(self,user,resource,arg1,arg2,acl_engine=self.acl_engine)
        self.log("authorize",[user,resource,arg1,arg2,rc],debug=True)
        return rc

    def build_iso(self,iso=None,profiles=None,systems=None,tempdir=None,distro=None,standalone=None,source=None, exclude_dns=None):
        builder = action_buildiso.BuildIso(self._config)
        return builder.run(
           iso=iso, profiles=profiles, systems=systems, tempdir=tempdir, distro=distro, standalone=standalone, source=source, exclude_dns=exclude_dns
        )

    def hardlink(self):
        linker = action_hardlink.HardLinker(self._config)
        return linker.run()

    def replicate(self, cobbler_master = None, sync_all=False, sync_kickstarts=False, sync_trees=False, sync_repos=False, sync_triggers=False, systems=False):
        """
        Pull down metadata from a remote cobbler server that is a master to this server.
        Optionally rsync data from it.
        """
        replicator = action_replicate.Replicate(self._config)
        return replicator.run(
              cobbler_master = cobbler_master,
              sync_all = sync_all,
              sync_kickstarts = sync_kickstarts,
              sync_trees = sync_trees,
              sync_repos = sync_repos,
              sync_triggers = sync_triggers,
              include_systems = systems
        )

    def report(self, report_what = None, report_name = None, report_type = None, report_fields = None, report_noheaders = None):
        """
        Report functionality for cobbler
        """
        reporter = action_report.Report(self._config)
        return reporter.run(report_what = report_what, report_name = report_name,\
                            report_type = report_type, report_fields = report_fields,\
                            report_noheaders = report_noheaders)

    def get_kickstart_templates(self):
        return utils.get_kickstar_templates(self)

    def power_on(self, system, user=None, password=None):
        """
        Powers up a system that has power management configured.
        """
        return action_power.PowerTool(self._config,system,self,user,password).power("on")

    def power_off(self, system, user=None, password=None):
        """
        Powers down a system that has power management configured.
        """
        return action_power.PowerTool(self._config,system,self,user,password).power("off")

    def reboot(self,system, user=None, password=None):
        """
        Cycles power on a system that has power management configured.
        """
        self.power_off(system, user, password)
        time.sleep(5)
        return self.power_on(system, user, password)

    def manage_deployment(self, system, virt_host=None, virt_group=None, method=None, operation=None):
        """
        Deploys a system to the virtual host or virtual group
        """

        if not operation in [ "install", "uninstall", "start", "reboot", "shutdown", "unplug" ]:
            raise CX("operation must be one of: install, uninstall, start, reboot, shutdown, or unplug")


        # FIXME: move into action_deploy once complete.
        if isinstance(system, basestring):
            system = self.find_system(system)
        if method is None:
            method = self.settings().default_deployment_method
        method = "deploy_%s" % method
        mod = self.get_module_by_name(method)
        if mod is None or mod.register() != "deploy":
            raise CX("no deployment module found named: %s" % method)


        if operation == "install":

            # this should raise a CX if anything bad happens and return
            # the name of the host successfully deployed to
            actual_host = mod.deploy(self,system,virt_host=virt_host,virt_group=virt_group)
            # update the system record of the guest 
            # so we have a record of where the guest is installed
            system.set_virt_host(actual_host)
            self.add_system(system)
            # now update the system record of the host so we know what guests
            # run on it
            host_record = self.find_system(name=actual_host)
            guests = host_record.virt_guests
            guests.append(system.name)
            host_record.set_virt_guests(guests)
            self.add_system(host_record)

        else:

            if system.virt_host == "":
               raise CX("--virt-host attribute unset for guest system (%s), don't know where this guest is hosted" % (system.name))
            host_record = self.find_system(name=system.virt_host)
            if host_record is None:
               raise CX("couldn't find the virtual host system record for (%s)" % system.virt_host)
            if host_record.hostname == "":
               raise CX("hostname field for host (%s) not set" % host_record.name)

            # this will raise an exception if it fails
            mod.general_operation(self,host_record.hostname,system.name,operation)

            if operation == "uninstall":
                # remove the guest from the list of machines running on this host
                guests = host_record.virt_guests
                guests.remove(system.name)
                host_record.set_virt_guests(guests)
                self.add_system(host_record)
                # clear the virt host for the guest
                system.set_virt_host("")
                self.add_system(system)
            else:
                # we may wish to save the state of the guest in the record
                # later, but since that is so likely to be managed out of band
                # we will skip it for now.
                pass

        return True

    def get_os_details(self):
        return (self.dist, self.os_version)


