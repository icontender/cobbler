"""
Enables the "cobbler import" command to seed cobbler
information with available distribution from rsync mirrors
and mounted DVDs.  

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

from cexceptions import *
import os
import os.path
import traceback
import sub_process
import glob
import api
import utils
import shutil
import re
from utils import _

import item_repo

# FIXME: add --quiet depending on if not --verbose?
RSYNC_CMD =  "rsync -a %s '%s' %s/ks_mirror/%s --exclude-from=/etc/cobbler/rsync.exclude --progress"

class Importer:

   def __init__(self,api,config,mirror,mirror_name,network_root=None,kickstart_file=None,rsync_flags=None,arch=None,breed=None,os_version=None):
       """
       Performs an import of a install tree (or trees) from the given
       mirror address.  The prefix of the distro is to be specified
       by mirror name.  For instance, if FC-6 is given, FC-6-xen-i386
       would be a potential distro that could be created.  For content
       available on external servers via a known nfs:// or ftp:// or
       http:// path, we can import without doing rsync mirorring to 
       cobbler's http directory.  This is explained in more detail 
       in the manpage.  Leave network_root to None if want mirroring.
       """
       self.api = api
       self.config = config
       self.mirror = mirror
       self.mirror_name = mirror_name
       self.network_root = network_root 
       self.distros  = config.distros()
       self.profiles = config.profiles()
       self.systems  = config.systems()
       self.settings = config.settings()
       self.kickstart_file = kickstart_file
       self.rsync_flags = rsync_flags
       self.arch = arch
       self.breed = breed
       self.os_version = os_version

   # ========================================================================

   def run(self):

       """
       This contains the guts of the import command.
       """


       # both --import and --name are required arguments

       if self.mirror is None:
           raise CX(_("import failed.  no --mirror specified"))
       if self.mirror_name is None:
           raise CX(_("import failed.  no --name specified"))

       # if --arch is supplied, validate it to ensure it's valid

       if self.arch is not None:
           self.arch = self.arch.lower()
           if self.arch == "x86":
               # be consistent
               self.arch = "i386"
           if self.arch not in [ "i386", "ia64", "ppc", "ppc64", "s390", "s390x", "x86_64", ]:
               raise CX(_("arch must be i386, ia64, ppc, ppc64, s390, s390x or x86_64"))

       # if we're going to do any copying, set where to put things
       # and then make sure nothing is already there.

       mpath = os.path.join(self.settings.webdir, "ks_mirror", self.mirror_name)
       if os.path.exists(mpath) and self.arch is None:
           # FIXME : Raise exception even when network_root is given ?
           raise CX(_("Something already exists at this import location (%s).  You must specify --arch to avoid potentially overwriting existing files.") % mpath)

       # import takes a --kickstart for forcing selection that can't be used in all circumstances
 
       if self.kickstart_file and not self.breed:
           raise CX(_("Kickstart file can only be specified when a specific breed is selected"))

       if self.os_version and not self.breed:
           raise CX(_("OS version can only be specified when a specific breed is selected"))

       if self.breed and self.breed.lower() not in [ "redhat", "debian", "ubuntu", "windows", "suse" ]:

           raise CX(_("Supplied import breed is not supported"))
 
       # if --arch is supplied, make sure the user is not importing a path with a different
       # arch, which would just be silly.  
       # if the user specifies --arch-i386 and name has (x86) the exception will get raised

       if self.arch:
           # append the arch path to the name if the arch is not already
           # found in the name.
           for x in [ "i386", "ia64", "ppc", "ppc64", "s390", "s390x", "x86_64", "x86", ]:
               if self.mirror_name.lower().find(x) != -1:
                   if self.arch != x :
                       raise CX(_("Architecture found on pathname (%s) does not fit the one given in command line (%s)")%(x,self.arch))
                   break
           else:
               # FIXME : This is very likely removed later at get_proposed_name, and the guessed arch appended again
               self.mirror_name = self.mirror_name + "-" + self.arch

       # make the output path and mirror content but only if not specifying that a network
       # accessible support location already exists (this is --available-as on the command line)

       if self.network_root is None:
 
           # we need to mirror (copy) the files 

           self.path = os.path.normpath( "%s/ks_mirror/%s" % (self.settings.webdir, self.mirror_name) )
           self.mkdir(self.path)

           # prevent rsync from creating the directory name twice
           # if we are copying via rsync

           if not self.mirror.endswith("/"):
               self.mirror = "%s/" % self.mirror 

           if self.mirror.startswith("http://") or self.mirror.startswith("ftp://") or self.mirror.startswith("nfs://"):

               # http mirrors are kind of primative.  rsync is better.
               # that's why this isn't documented in the manpage and we don't support them.
               # TODO: how about adding recursive FTP as an option?

               raise CX(_("unsupported protocol"))

           else:

               # good, we're going to use rsync.. 
               # we don't use SSH for public mirrors and local files.
               # presence of user@host syntax means use SSH

               spacer = ""
               if not self.mirror.startswith("rsync://") and not self.mirror.startswith("/"):
                   spacer = ' -e "ssh" '
               rsync_cmd = RSYNC_CMD
               if self.rsync_flags:
                   rsync_cmd = rsync_cmd + " " + self.rsync_flags

               # kick off the rsync now

               self.run_this(rsync_cmd, (spacer, self.mirror, self.settings.webdir, self.mirror_name))

       else:

           # rather than mirroring, we're going to assume the path is available
           # over http, ftp, and nfs, perhaps on an external filer.  scanning still requires
           # --mirror is a filesystem path, but --available-as marks the network path
          
           if not os.path.exists(self.mirror):
               raise CX(_("path does not exist: %s") % self.mirror)

           # find the filesystem part of the path, after the server bits, as each distro
           # URL needs to be calculated relative to this. 

           if not self.network_root.endswith("/"):
               self.network_root = self.network_root + "/"
           self.path = os.path.normpath( self.mirror )
           valid_roots = [ "nfs://", "ftp://", "http://" ]
           for valid_root in valid_roots:
               if self.network_root.startswith(valid_root):
                   break
           else:
               raise CX(_("Network root given to --available-as must be nfs://, ftp://, or http://"))
           if self.network_root.startswith("nfs://"):
               try:
                   (a,b,rest) = self.network_root.split(":",3)
               except:
                   raise CX(_("Network root given to --available-as is missing a colon, please see the manpage example."))

       # now walk the filesystem looking for distributions that match certain patterns

       print _("---------------- (adding distros)")
       distros_added = []
       # FIXME : search below self.path for isolinux configurations or known directories from TRY_LIST
       os.path.walk(self.path, self.distro_adder, distros_added)

       # find out if we can auto-create any repository records from the install tree

       if self.network_root is None:
           print _("---------------- (associating repos)")
           # FIXME: this automagic is not possible (yet) without mirroring 
           self.repo_finder(distros_added)

       # find the most appropriate answer files for each profile object

       print _("---------------- (associating kickstarts)")
       self.kickstart_finder(distros_added) 

       # ensure bootloaders are present
       self.api.pxegen.copy_bootloaders()

       return True

   # ----------------------------------------------------------------------

   def mkdir(self, dir):

       """
       A more tolerant mkdir.
       FIXME: use the one in utils.py (?)
       """

       try:
           os.makedirs(dir)
       except OSError , ex:
           if ex.strerror == "Permission denied":
               raise CX(_("Permission denied at %s")%dir)
       except:
           pass

   # ----------------------------------------------------------------------

   def run_this(self, cmd, args):

       """
       A simple wrapper around subprocess calls.
       """

       my_cmd = cmd % args
       print _("- %s") % my_cmd
       rc = sub_process.call(my_cmd,shell=True,close_fds=True)
       if rc != 0:
          raise CX(_("Command failed"))

   # =======================================================================

   def kickstart_finder(self,distros_added):

       """
       For all of the profiles in the config w/o a kickstart, use the
       given kickstart file, or look at the kernel path, from that, 
       see if we can guess the distro, and if we can, assign a kickstart 
       if one is available for it.
       """

       for profile in self.profiles:
           distro = self.distros.find(name=profile.distro)
           if distro is None or not (distro in distros_added):
               # print _("- skipping distro %s since it wasn't imported this time") % profile.distro
               continue

           kdir = os.path.dirname(distro.kernel)   

           importer = import_factory(kdir,self.path,self.breed)

           if self.kickstart_file == None:
               # This is the new method to use, you must set ks file in the importer subclass
               if importer.breed == 'suse':
                   if importer.ksfile:
                       profile.set_kickstart(importer.ksfile)
                   if importer.comment:
                      distro.set_comment(importer.comment)
                   if importer.os_version:
                      distro.set_os_version(importer.os_version)   
                # This is the old method to use, since I didn't want to touch this yet
               else:
                  for rpm in importer.get_release_files():
                     # FIXME : This redhat specific check should go into the importer.find_release_files method
                     if rpm.find("notes") != -1:
                        continue
                     results = importer.scan_pkg_filename(rpm)
                     if results is None:
                        continue
                     (flavor, major, minor) = results
                     # print _("- finding default kickstart template for %(flavor)s %(major)s") % { "flavor" : flavor, "major" : major }
                     version , ks = importer.set_variance(flavor, major, minor, distro.arch)
                     if self.os_version:
                         if self.os_version != version:
                             raise CX(_("CLI version differs from tree : %s vs. %s") % (self.os_version,version))
                     ds = importer.get_datestamp()
                     distro.set_comment("%s.%s" % (version, int(minor)))
                     distro.set_os_version(version)
                     if ds is not None:
                        distro.set_tree_build_time(ds)
                     profile.set_kickstart(ks)
                     self.profiles.add(profile,save=True)

           self.configure_tree_location(distro,importer)
           self.distros.add(distro,save=True) # re-save
           self.api.serialize()

   # ==========================================================================


   def configure_tree_location(self, distro, importer):

       """
       Once a distribution is identified, find the part of the distribution
       that has the URL in it that we want to use for kickstarting the
       distribution, and create a ksmeta variable $tree that contains this.
       """

       base = importer.get_rootdir()

       if self.network_root is None:
           dest_link = os.path.join(self.settings.webdir, "links", distro.name)
           # create the links directory only if we are mirroring because with
           # SELinux Apache can't symlink to NFS (without some doing)
           if not os.path.exists(dest_link):
               try:
                   os.symlink(base, dest_link)
               except:
                   # this shouldn't happen but I've seen it ... debug ...
                   print _("- symlink creation failed: %(base)s, %(dest)s") % { "base" : base, "dest" : dest_link }
           # how we set the tree depends on whether an explicit network_root was specified
           tree = "http://@@http_server@@/cblr/links/%s" % (distro.name)
           importer.set_install_tree( distro, tree)
       else:
           # where we assign the kickstart source is relative to our current directory
           # and the input start directory in the crawl.  We find the path segments
           # between and tack them on the network source path to find the explicit
           # network path to the distro that Anaconda can digest.  
           tail = self.path_tail(self.path, base)
           tree = self.network_root[:-1] + tail
           importer.set_install_tree( distro, tree)

       # print _("- tree: %s") % meta["tree"]

   # ============================================================================

   def path_tail(self, apath, bpath):
       """ 
       Given two paths (B is longer than A), find the part in B not in A
       """
       position = bpath.find(apath)
       if position != 0:
           print "%s, %s, %s" % (apath, bpath, position)
           #raise CX(_("Error: possible symlink traversal?: %s") % bpath)
           print _("- warning: possible symlink traversal?: %s") % bpath
       rposition = position + len(self.mirror)
       result = bpath[rposition:]
       if not result.startswith("/"):
           result = "/" + result
       return result

   # ======================================================================
   
   def repo_finder(self,distros_added):

       """
       This routine looks through all distributions and tries to find 
       any applicable repositories in those distributions for post-install
       usage.
       """
       
       for distro in distros_added:
           print _("- traversing distro %s") % distro.name
           # FIXME : Shouldn't decide this the value of self.network_root ?
           if distro.kernel.find("ks_mirror") != -1:
               basepath = os.path.dirname(distro.kernel)
               importer = import_factory(basepath,self.path,self.breed)
               top = importer.get_rootdir()
               print _("- descent into %s") % top
               if distro.breed in [ "debian" , "ubuntu" ]:
                   importer.process_repos( self , distro )
               #elif distro.breed == 'suse':
                  # Should suse be processing repos?
                 # continue
               else:
                   # FIXME : The location of repo definition is known from breed
                   os.path.walk(top, self.repo_scanner, distro)
           else:
               print _("- this distro isn't mirrored")

   # ========================================================================


   def repo_scanner(self,distro,dirname,fnames):

       """
       This is an os.path.walk routine that looks for potential yum repositories
       to be added to the configuration for post-install usage.
       """
       
       matches = {}
       for x in fnames:
          if x == "base" or x == "repodata":
               print "- processing repo at : %s" % dirname
               # only run the repo scanner on directories that contain a comps.xml
               gloob1 = glob.glob("%s/%s/*comps*.xml" % (dirname,x))
               if len(gloob1) >= 1:
                   if matches.has_key(dirname):
                       print _("- looks like we've already scanned here: %s") % dirname
                       continue
                   print _("- need to process repo/comps: %s") % dirname
                   self.process_comps_file(dirname, distro)
                   matches[dirname] = 1
               else:
                   print _("- directory %s is missing xml comps file, skipping") % dirname
                   continue

   # =======================================================================================



   def process_comps_file(self, comps_path, distro):
       """
       When importing Fedora/EL certain parts of the install tree can also be used
       as yum repos containing packages that might not yet be available via updates
       in yum.  This code identifies those areas.
       """

       processed_repos = {}

       masterdir = "repodata"
       if not os.path.exists(os.path.join(comps_path, "repodata")):
           # older distros...
           masterdir = "base"

       # print _("- scanning: %(path)s (distro: %(name)s)") % { "path" : comps_path, "name" : distro.name }

       # figure out what our comps file is ...
       print _("- looking for %(p1)s/%(p2)s/*comps*.xml") % { "p1" : comps_path, "p2" : masterdir }
       files = glob.glob("%s/%s/*comps*.xml" % (comps_path, masterdir))
       if len(files) == 0:
           print _("- no comps found here: %s") % os.path.join(comps_path, masterdir)
           return # no comps xml file found

       # pull the filename from the longer part
       comps_file = files[0].split("/")[-1]

       try:

           # store the yum configs on the filesystem so we can use them later.
           # and configure them in the kickstart post, etc

           # print "- possible source repo match"
           counter = len(distro.source_repos)

           # find path segment for yum_url (changing filesystem path to http:// trailing fragment)
           seg = comps_path.rfind("ks_mirror")
           urlseg = comps_path[seg+10:]
           # print "- segment: %s" % urlseg

           # write a yum config file that shows how to use the repo.
           if counter == 0:
               dotrepo = "%s.repo" % distro.name
           else:
               dotrepo = "%s-%s.repo" % (distro.name, counter)

           fname = os.path.join(self.settings.webdir, "ks_mirror", "config", "%s-%s.repo" % (distro.name, counter))

           repo_url = "http://@@http_server@@/cobbler/ks_mirror/config/%s-%s.repo" % (distro.name, counter)
           
           repo_url2 = "http://@@http_server@@/cobbler/ks_mirror/%s" % (urlseg)
           
           distro.source_repos.append([repo_url,repo_url2])

           # NOTE: the following file is now a Cheetah template, so it can be remapped
           # during sync, that's why we have the @@http_server@@ left as templating magic.
           # repo_url2 is actually no longer used. (?)

           # print _("- url: %s") % repo_url
           config_file = open(fname, "w+")
           config_file.write("[core-%s]\n" % counter)
           config_file.write("name=core-%s\n" % counter)
           config_file.write("baseurl=http://@@http_server@@/cobbler/ks_mirror/%s\n" % (urlseg))
           config_file.write("enabled=1\n")
           config_file.write("gpgcheck=0\n")
           config_file.write("priority=1\n")
           config_file.close()

           # don't run creatrepo twice -- this can happen easily for Xen and PXE, when
           # they'll share same repo files.

           if not processed_repos.has_key(comps_path):
               utils.remove_yum_olddata(comps_path)
               #cmd = "createrepo --basedir / --groupfile %s %s" % (os.path.join(comps_path, masterdir, comps_file), comps_path)
               cmd = "createrepo -c cache --groupfile %s %s" % (os.path.join(comps_path, masterdir, comps_file), comps_path)
               print _("- %s") % cmd
               sub_process.call(cmd,shell=True,close_fds=True)
               processed_repos[comps_path] = 1
               # for older distros, if we have a "base" dir parallel with "repodata", we need to copy comps.xml up one...
               p1 = os.path.join(comps_path, "repodata", "comps.xml")
               p2 = os.path.join(comps_path, "base", "comps.xml")
               if os.path.exists(p1) and os.path.exists(p2):
                   print _("- cp %(p1)s %(p2)s") % { "p1" : p1, "p2" : p2 }
                   shutil.copyfile(p1,p2)

       except:
           print _("- error launching createrepo, ignoring...")
           traceback.print_exc()


   # ========================================================================

   def distro_adder(self,foo,dirname,fnames):

       """
       This is an os.path.walk routine that finds distributions in the directory
       to be scanned and then creates them.
       """
       # SLES9 has the possibility of having multiple kernels if a service pack is integrated into a DVD
       # Of course this can only occur if the user made a DVD from the 9 CDs if originally came with
       # We will want to only import the Service Pack kernel since it has the latest network drivers
       # SLES10 is completely different and is searchable by normal standards
       
       # I think if we find multiple kernels we should break out and ask the user which one to use
       # Going to skip SLES9 for now

       # FIXME: If there are more than one kernel or initrd image on the same directory,
       # results are unpredictable

       initrd = None
       kernel = None
       
       # keep everything lower case just in case 
       # To search for new distros, add your ramdisk/kernel info here
       d_ramdisk = [ 'initrd', 'ramdisk.image.gz' ]
       d_kernel = [ 'linux', 'vmlinuz', 'kernel.img', 'initrd' ]

       

       for x in fnames:

           fullname = os.path.join(dirname,x)
           if os.path.islink(fullname) and os.path.isdir(fullname):
              if fullname.startswith(self.path):
                  # Prevent infinite loop with Sci Linux 5
                  print "- warning: avoiding symlink loop"
                  continue
              print "- following symlink: %s" % fullname
              os.path.walk(fullname, self.distro_adder, foo)
          
           # I wasn't sure if I was getting a filename path or just the filename
           # If its just a filename we can change fname back to x and remove the line below
           fname = os.path.basename(x)
           
           # This is where we will search for the kernel and ramdisk
           if fname.lower() in d_ramdisk:
              initrd = os.path.join(dirname,x)
           elif fname in d_kernel:
              kernel = os.path.join(dirname,x)

           

           #print 'initrd = %s' % (initrd)
           #print 'kernel = %s' % (kernel)
           #print 'filename = %s' %(x)    

           if initrd is not None and kernel is not None and dirname.find("isolinux") == -1:
               adtl = self.add_entry(dirname,kernel,initrd)
               if adtl != None:
                   foo.extend(adtl)
                   # Not resetting these values causes problems 
                   # importing debian media because there are remaining items in fnames
                   initrd = None
                   kernel = None
   
   # ========================================================================

   def add_entry(self,dirname,kernel,initrd):

       """
       When we find a directory with a valid kernel/initrd in it, create the distribution objects
       as appropriate and save them.  This includes creating xen and rescue distros/profiles
       if possible.
       """
       # lets just get the name and arch from the importer object if we can
       importer = import_factory(dirname,self.path)
       if importer.get_arch():
           proposed_arch = importer.get_arch()
       if importer.get_osname:
           proposed_name = importer.get_osname()
       
       else:
           proposed_name = self.get_proposed_name(dirname)
           proposed_arch = self.get_proposed_arch(dirname)
       
       if self.network_root:
           kopts = importer.get_kopts(self.network_root)
       else:
           kopts = importer.get_kopts(self.mirror)
            
           
       if self.arch and proposed_arch and self.arch != proposed_arch:
           raise CX(_("Arch from pathname (%s) does not match with supplied one %s")%(proposed_arch,self.arch))


       importer = import_factory(dirname,self.path,self.breed)

       
       if self.breed and self.breed != importer.breed:
           raise CX( _("Requested breed (%s); breed found is %s") % ( self.breed , breed ) )


       
       archs = importer.learn_arch_from_tree()

       if not archs:
           if self.arch:
               archs.append( self.arch )
       else:
            if self.arch and self.arch not in archs:
               raise CX(_("Given arch (%s) not found on imported tree %s")%(self.arch,importer.get_pkgdir()))


       if proposed_arch:
           if archs and proposed_arch not in archs:
               print _("Warning: arch from pathname (%s) not found on imported tree %s") % (proposed_arch,importer.get_pkgdir())
               return

           archs = [ proposed_arch ]

       if importer.breed == "ubuntu" and dirname.find("ubuntu-installer") == -1:
           print _("- skipping entry, there aren't netboot images")
           return


       if len(archs)>1:
           if importer.breed in [ "redhat" ]:
               print _("Warning: directory %s holds multiple arches : %s") % (dirname, archs) 
               return
           print _("- Warning : Multiple archs found : %s") % (archs)

       distros_added = []

       for pxe_arch in archs:

           name = proposed_name + "-" + pxe_arch
           existing_distro = self.distros.find(name=name)

           if existing_distro is not None:
               print _("- warning: skipping import, as distro name already exists: %s") % name
               continue

           else:
               print _("- creating new distro: %s") % name
               distro = self.config.new_distro()
           
           if name.find("-autoboot") != -1:
               # this is an artifact of some EL-3 imports
               continue

           distro.set_name(name)
           distro.set_kernel(kernel)
           distro.set_kernel_options(kopts)
           distro.set_initrd(initrd)
           distro.set_arch(pxe_arch)
           distro.set_breed(importer.breed)
           # If a version was supplied on command line, we set it now
           if self.os_version:
               distro.set_os_version(self.os_version)
           distro.source_repos = []

           self.distros.add(distro,save=True)
           distros_added.append(distro)       

           existing_profile = self.profiles.find(name=name) 

           # see if the profile name is already used, if so, skip it and 
           # do not modify the existing profile

           if existing_profile is None:
               print _("- creating new profile: %s") % name 
               #FIXME: The created profile holds a default kickstart, and should be breed specific
               profile = self.config.new_profile()
           else:
               print _("- skipping existing profile, name already exists: %s") % name
               continue

           # save our minimal profile which just points to the distribution and a good
           # default answer file

           profile.set_name(name)
           profile.set_distro(name)
           if self.kickstart_file:
               profile.set_kickstart(self.kickstart_file)
           else:
               profile.set_kickstart(importer.ks)

           # depending on the name of the profile we can define a good virt-type
           # for usage with koan

           if name.find("-xen") != -1:
               profile.set_virt_type("xenpv")
           else:
               profile.set_virt_type("qemu")

           # save our new profile to the collection

           self.profiles.add(profile,save=True)

           # Create a rescue image as well, if this is not a xen distro
           # but only for red hat profiles
           # Might hadve to do this for suse as well

           if name.find("-xen") == -1 and (importer.breed == "redhat" or importer.breed == "suse"):
               rescue_name = 'rescue-' + name
               existing_profile = self.profiles.find(name=rescue_name)

               if existing_profile is None:
                   print _("- creating new profile: %s") % rescue_name
                   profile = self.config.new_profile()
               else:
                   continue

               profile.set_name(rescue_name)
               profile.set_distro(name)
               profile.set_virt_type("qemu")
               profile.kernel_options['rescue'] = None
               profile.kickstart = '/etc/cobbler/pxerescue.ks'

               self.profiles.add(profile,save=True)

       self.api.serialize()
       return distros_added

   # ========================================================================

   def get_proposed_name(self,dirname):

       """
       Given a directory name where we have a kernel/initrd pair, try to autoname
       the distribution (and profile) object based on the contents of that path
       """

       if self.network_root is not None:
          name = self.mirror_name + "-".join(self.path_tail(os.path.dirname(self.path),dirname).split("/"))
       else:
          # remove the part that says /var/www/cobbler/ks_mirror/name
          name = "-".join(dirname.split("/")[5:])

       # These are all Ubuntu's doing, the netboot images are buried pretty
       # deep. ;-) -JC
       name = name.replace("-netboot","")
       name = name.replace("-ubuntu-installer","")
       name = name.replace("-amd64","")
       name = name.replace("-i386","")

       # we know that some kernel paths should not be in the name
       #print 'dirname = %s ' % (dirname)
       name = name.replace("-images","")
       name = name.replace("-pxeboot","")  
       name = name.replace("-install","")  
       name = name.replace("boot", "")
       name = name.replace("loader", "")
       # some paths above the media root may have extra path segments we want
       # to clean up

       name = name.replace("-os","")
       name = name.replace("-tree","")
       name = name.replace("var-www-cobbler-", "")
       name = name.replace("ks_mirror-","")
       name = name.replace("--","-")

       # remove any architecture name related string, as real arch will be appended later

       name = name.replace("chrp","ppc64")

       for separator in [ '-' , '_'  , '.' ] :
         for arch in [ "i386" , "x86_64" , "ia64" , "ppc64", "ppc32", "ppc", "x86" , "s390x", "s390" , "386" , "amd" ]:
           name = name.replace("%s%s" % ( separator , arch ),"")

       return name

   # ========================================================================

   def get_proposed_arch(self,dirname):
       """
       Given an directory name, can we infer an architecture from a path segment?
       """

       if dirname.find("x86_64") != -1 or dirname.find("amd") != -1:
          return "x86_64"
       if dirname.find("ia64") != -1:
          return "ia64"
       if dirname.find("i386") != -1 or dirname.find("386") != -1 or dirname.find("x86") != -1:
          return "i386"
       if dirname.find("s390x") != -1:
          return "s390x"
       if dirname.find("i586") != -1:
          return "i586"
       if dirname.find("s390") != -1:
          return "s390"
       if dirname.find("ppc64") != -1 or dirname.find("chrp") != -1:
          return "ppc64"
       if dirname.find("ppc32") != -1:
          return "ppc"
       if dirname.find("ppc") != -1:
          return "ppc"
       return None

# ==============================================


def guess_breed(kerneldir,path,cli_breed):

    """
    This tries to guess the distro. Traverses from kernel dir to imported root checking 
    for distro signatures, which are the locations in media where the search for release 
    packages should start.  When a debian/ubuntu pool is found, the upper directory should 
    be checked to get the real breed. If we are on a real media, the upper directory will 
    be at the same level, as a local '.' symlink
    The lowercase names are required for fat32/vfat filesystems
    """
    signatures = [
       [ 'pool'        , "debian" ],
       [ 'RedHat/RPMS' , "redhat" ],
       [ 'RedHat/rpms' , "redhat" ],
       [ 'RedHat/Base' , "redhat" ],
       [ 'Fedora/RPMS' , "redhat" ],
       [ 'Fedora/rpms' , "redhat" ],
       [ 'CentOS/RPMS' , "redhat" ],
       [ 'CentOS/rpms' , "redhat" ],
       [ 'CentOS'      , "redhat" ],
       [ 'Packages'    , "redhat" ],
       [ 'Fedora'      , "redhat" ],
       [ 'Server'      , "redhat" ],
       [ 'Client'      , "redhat" ],
       [ 'isolinux.bin', None ],
       [ 'suse'        , "suse" ],
       ]
    guess = None

    while kerneldir != os.path.dirname(path) :
        # print _("- scanning %s for distro signature") % kerneldir
        for (x, breedguess) in signatures:
            d = os.path.join( kerneldir , x )
            if os.path.exists( d ):
                guess = breedguess
                break
        if guess: 
            break

        kerneldir = os.path.dirname(kerneldir)
    else:
        if cli_breed:
            print _("Warning: No distro signature for kernel at %s, using value from command line") % kerneldir
            return cli_breed , ( kerneldir , None )
        raise CX( _("No distro signature for kernel at %s") % kerneldir )

    if guess == "debian" :
        for suite in [ "debian" , "ubuntu" ] :
            # NOTE : Although we break the loop after the first match, 
            # multiple debian derived distros can actually live at the same pool -- JP
            d = os.path.join( kerneldir , suite )
            if os.path.islink(d) and os.path.isdir(d):
                if os.path.realpath(d) == os.path.realpath(kerneldir):
                    return suite , ( kerneldir , x )
            if os.path.basename( kerneldir ) == suite :
                return suite , ( kerneldir , x )

    return guess , ( kerneldir , x )

# ============================================================


def import_factory(kerneldir,path,cli_breed):
    """
    Given a directory containing a kernel, return an instance of an Importer
    that can be used to complete the import.
    """

    breed , rootdir = guess_breed(kerneldir,path,cli_breed)
    # NOTE : The guess_breed code should be included in the factory, in order to make 
    # the real root directory available, so allowing kernels at different levels within 
    # the same tree (removing the isolinux rejection from distro_adder) -- JP

    if rootdir[1]:
        print _("- found content (breed=%s) at %s") % (breed,os.path.join( rootdir[0] , rootdir[1] ) )
    else:
        print _("- found content (breed=%s) at %s") % (breed,rootdir[0] )
    if cli_breed:
        if cli_breed != breed:
            raise CX( _("Requested breed (%s); breed found is %s") % ( cli_breed , breed ) )
        breed = cli_breed

    if breed == "redhat":
       return RedHatImporter(rootdir)
    elif breed == "debian":
       return DebianImporter(rootdir)
    elif breed == "ubuntu":
       return UbuntuImporter(rootdir)
    elif breed == "suse":
       return SuseImporter(rootdir)
    elif breed:
       raise CX(_("Unknown breed %s")%breed)
    else:
       raise CX(_("No breed given"))



class BaseImporter:
   """
   Base class for distribution specific importer code.
   """

   # FIXME : Rename learn_arch_from_tree into guess_arch and simplify. 
   # FIXME : Drop package extension check and make a single search for all names.
   # FIXME:  Next methods to be moved here: kickstart_finder TRY_LIST loop

   # ===================================================================
   arch = None
   osname = None
   breed = None
   datestamp = None
   ksfile = None
   os_version = None
   comment = None
   kopts = ''
   
   def get_kopts(self, dirname):
       #Kernel options are a space delimited list,
       # like 'a=b c=d e=f g h i=j' or a hash.
       # You need to override this method if you plan on having kernel options for your distro
       return self.kopts
   def arch_walker(self,foo,dirname,fnames):
       """
       See docs on learn_arch_from_tree.

       The TRY_LIST is used to speed up search, and should be dropped for default importer
       Searched kernel names are kernel-header, linux-headers-, kernel-largesmp, kernel-hugemem
       
       This method is useful to get the archs, but also to package type and a raw guess of the breed
       """
 
       # try to find a kernel header RPM and then look at it's arch.
       for x in fnames:
           if self.match_kernelarch_file(x):
               # print _("- kernel header found: %s") % x
               for arch in [ "i386" , "x86_64" , "ia64" , "ppc64", "ppc", "s390", "s390x", "i586" ]:
                   if x.find(arch) != -1:
                       foo[arch] = 1
               for arch in [ "i686" , "amd64" ]:
                   if x.find(arch) != -1:
                       foo[arch] = 1
   
   # ===================================================================
   
   def get_os_version(self):
      return self.os_version

   def get_comment(self):
      return self.comment

   def get_arch(self):
       # you can either override this function or just set self.arch somewhere within your subclass
       # You will want to set self.arch as future implementations get the arch this way 
       return self.arch
       
   def get_ksfile(self):
       # you can either override this function or just set self.ksfile somewhere within your subclass
       # You will want to set self.ksfile as future implementations get the ksfile this way 
       
       return self.ksfile
   def get_osname(self):
     # you can either override this function or just set self.osname somewhere within your subclass
       # You will want to set self.osname as future implementations get the osname this way 
      
       return self.osname
       
   
   def get_rootdir(self):
       return self.rootdir
   
   # ===================================================================

   def get_pkgdir(self):
       if not self.pkgdir:
           return None
       return os.path.join(self.get_rootdir(),self.pkgdir)
   
   # ===================================================================

   def set_install_tree(self, distro, url):
       distro.ks_meta["tree"] = url
   
   # ===================================================================

   def learn_arch_from_tree(self):
       """ 
       If a distribution is imported from DVD, there is a good chance the path doesn't 
       contain the arch and we should add it back in so that it's part of the 
       meaningful name ... so this code helps figure out the arch name.  This is important 
       for producing predictable distro names (and profile names) from differing import sources
       """
       # You may want to override this function if you don't need it
       result = {}
       # FIXME : this is called only once, should not be a walk      
       if self.get_pkgdir():
           os.path.walk(self.get_pkgdir(), self.arch_walker, result)      
           # print _("- architectures found at %s: %s") % ( self.get_pkgdir(), result.keys() )
           # just because the packages end with (i686 or i586) we still want to consider them as i386
           # there is a difference with these numbers but they all run on x86 hardware
       if result.pop("amd64",False):
           result["x86_64"] = 1
        
       elif result.pop("i686",False):
           result["i386"] = 1
           
       elif result.pop("i586", False):
           result["i386"] = 1
           
       return result.keys()

   def get_datestamp(self):
       """
       Allows each breed to return its datetime stamp
       """
       return None
   # ===================================================================

   def __init__(self,(rootdir,pkgdir)):
       raise CX(_("ERROR - BaseImporter is an abstract class"))
   
   # ===================================================================

   def process_repos(self, main_importer, distro):
       raise exceptions.NotImplementedError

# ===================================================================
# ===================================================================
class SuseImporter ( BaseImporter ):
   def __init__(self,(rootdir,pkgdir)):
      self.breed = "suse"
      self.rootdir = rootdir
      self.pkgdir = pkgdir
      self._set_content_data()
      self._set_ksfile()
   
   def get_kopts(self, dirname):
       # this tells the autoyast where to get the distro files
       self.kopts = 'install=%s' % (dirname)
       return self.kopts
   def get_arch(self):
       # since the arch might be i586 we will want to return i386 instead
       if self.arch == 'i586':
           return 'i386'
       else:
           return self.arch
       
   def arch_walker(self,foo,dirname,fnames):
       # no need to iplement this since I can find the arch with the content file
       # However, I still need to override it to keep the base.arch_walker from running
       pass
       
   def learn_arch_from_tree(self):
       # Since I can get the arch from the content file I can just return it here
       #print "Look I found %s" % (self.arch)
       if self.arch == 'i586':
           self.arch = 'i386'
       
       return self.get_arch()
       
  # ================================================================
   
   def _get_content_data(self):
      # The content file tells everything we ever wanted to know about the 
      # the suse distro in the rootdir
      # Get everything except the SHA1 lines in the content file
     # Key         Content
    #PRODUCT      Product name
    #VERSION      Product version
    #VENDOR       Product vendor
    #LABEL        Source designation to be used in YaST
    #ARCH.<base>  Supported architectures for the base architecture
    #DEFAULTBASE  Default base architecture
    #DESCRDIR     The directory containing the package descriptions
    #DATADIR      The directory containing the packages
      content = {}
      
      file = os.path.join(self.get_rootdir(), "content")
      try:
         try:
            cfile = open(file)
            self.datestamp = float(os.path.getctime(file))
            for line in cfile.readlines():
               if line.find('SHA1') !=-1:
                  # don't care about these lines
                  continue
               else:
                  # {variable: value} format
                  # just put every line of the content file in the dict
                  # stuff in the content file is different for each release
                  data = re.split('\s', line)
                  variable = data.pop(0)
                  # remove white spaces although realisticlly we should do this in the regex
                  sep = ' '
                  value = ''
                  value = sep.join(data) 
                  value.lstrip()
                  value.rstrip()
                  content[variable] = value
                  #print variable + ' = ' + value
                  
                  
         except:
            print 'Could not open file ' + file
      finally:
         cfile.close()
         
      
      return content
   def _set_content_data(self):
      
      content = self._get_content_data()
    
      if content.has_key('DEFAULTBASE'):
         self.arch = content['DEFAULTBASE']
      elif content.has_key('BASEARCHS'):
         self.arch = content['BASEARCHS']
      else:
         # Could not find an arch
         self.arch = None
          
      # EXample: SHORTLABEL SLES 10 SP2
      # Example: LABEL openSUSE 11.1
      
      if content.has_key('SHORTLABEL'):
         self.osname = content['SHORTLABEL']
      elif content.has_key('LABEL'):
         self.osname = content['LABEL']
      else:
         # Could not find an os version
         self.osname = None
      
      
      # remove all the white spaces
      self.arch = self.arch.strip()
      self.osname = self.osname.rstrip()
      self.osname = self.osname.lstrip()
      self.osname = self.osname.replace(' ', '-')
      self.os_version = self.osname
      self.comment = self.osname
   def _set_ksfile(self):
       # suse 9 is so different we cant process here, maybe a contrib script would do 
      # the trick
      if self.osname.find('10') !=-1:
         self.ksfile = '/var/lib/cobbler/kickstarts/autoyast_suse10.ks'
      elif self.osname.find('11') !=-1:
         self.ksfile = '/var/lib/cobbler/kickstarts/autoyast_suse11.ks'
   
      
      else:
         print '- warning: could not use suse distro version'
         return None
      
class RedHatImporter ( BaseImporter ) :

   def __init__(self,(rootdir,pkgdir)):
       self.breed = "redhat"
       self.ks = "/var/lib/cobbler/kickstarts/default.ks"
       self.rootdir = rootdir
       self.pkgdir = pkgdir

   # ================================================================

   def get_release_files(self):
       data = glob.glob(os.path.join(self.get_pkgdir(), "*release-*"))
       data2 = []
       for x in data:
          b = os.path.basename(x)
          if b.find("fedora") != -1 or \
             b.find("redhat") != -1 or \
             b.find("centos") != -1:
                 data2.append(x)
       return data2

   # ================================================================

   def match_kernelarch_file(self, filename):
       """
       Is the given filename a kernel filename?
       """

       if not filename.endswith("rpm") and not filename.endswith("deb"):
           return False
       for match in ["kernel-header", "kernel-source", "kernel-smp", "kernel-largesmp", "kernel-hugemem", "linux-headers-", "kernel-devel", "kernel-"]:
           if filename.find(match) != -1:
               return True
       return False

   # ================================================================

   def scan_pkg_filename(self, rpm):
       """
       Determine what the distro is based on the release package filename.
       """

       rpm = os.path.basename(rpm)

       # if it looks like a RHEL RPM we'll cheat.
       # it may be slightly wrong, but it will be close enough
       # for RHEL5 we can get it exactly.
       
       for x in [ "4AS", "4ES", "4WS", "4common", "4Desktop" ]:
          if rpm.find(x) != -1:
             return ("redhat", 4, 0)
       for x in [ "3AS", "3ES", "3WS", "3Desktop" ]:
          if rpm.find(x) != -1:
             return ("redhat", 3, 0)
       for x in [ "2AS", "2ES", "2WS", "2Desktop" ]:
          if rpm.find(x) != -1:
             return ("redhat", 2, 0)

       # now get the flavor:
       flavor = "redhat"
       if rpm.lower().find("fedora") != -1:
          flavor = "fedora"
       if rpm.lower().find("centos") != -1:
          flavor = "centos"

       # get all the tokens and try to guess a version
       accum = []
       tokens = rpm.split(".")
       for t in tokens:
          tokens2 = t.split("-")
          for t2 in tokens2:
             try:
                 float(t2)
                 accum.append(t2)
             except:
                 pass

       major = float(accum[0])
       minor = float(accum[1])
       return (flavor, major, minor)

   def get_datestamp(self):
       """
       Based on a RedHat tree find the creation timestamp
       """
       base = self.get_rootdir()
       if os.path.exists("%s/.discinfo" % base):
           discinfo = open("%s/.discinfo" % base, "r")
           datestamp = discinfo.read().split("\n")[0]
           discinfo.close()
       else:
           return 0
       return float(datestamp)

   def set_variance(self, flavor, major, minor, arch):
  
       """
       find the profile kickstart and set the distro breed/os-version based on what
       we can find out from the rpm filenames and then return the kickstart
       path to use.
       """

       if flavor == "fedora":

           # this may actually fail because the libvirt/virtinst database
           # is not always up to date.  We keep a simplified copy of this
           # in codes.py.  If it fails we set it to something generic
           # and don't worry about it.

           try:
               os_version = "fedora%s" % int(major)
           except:
               os_version = "other"

       if flavor == "redhat" or flavor == "centos":

           if major <= 2:
                # rhel2.1 is the only rhel2
                os_version = "rhel2.1"
           else:
                try:
                    # must use libvirt version
                    os_version = "rhel%s" % (int(major))
                except:
                    os_version = "other"

       kickbase = "/var/lib/cobbler/kickstarts"
       # Look for ARCH/OS_VERSION.MINOR kickstart first
       #          ARCH/OS_VERSION next
       #          OS_VERSION next
       #          OS_VERSION.MINOR next
       #          ARCH/default.ks next
       #          FLAVOR.ks next
       kickstarts = [
           "%s/%s/%s.%i.ks" % (kickbase,arch,os_version,int(minor)), 
           "%s/%s/%s.ks" % (kickbase,arch,os_version), 
           "%s/%s.%i.ks" % (kickbase,os_version,int(minor)),
           "%s/%s.ks" % (kickbase,os_version),
           "%s/%s/default.ks" % (kickbase,arch),
           "%s/%s.ks" % (kickbase,flavor),
       ]
       for kickstart in kickstarts:
           if os.path.exists(kickstart):
               return os_version, kickstart

       major = int(major) 

       if flavor == "fedora":
           if major >= 8:
                return os_version , "/var/lib/cobbler/kickstarts/sample_end.ks"
           if major >= 6:
                return os_version , "/var/lib/cobbler/kickstarts/sample.ks"

       if flavor == "redhat" or flavor == "centos":
           if major >= 5:
                return os_version , "/var/lib/cobbler/kickstarts/sample.ks"

           return os_version , "/var/lib/cobbler/kickstarts/legacy.ks"

       print _("- warning: could not use distro specifics, using rhel 4 compatible kickstart")
       return None , "/var/lib/cobbler/kickstarts/legacy.ks"

class DebianImporter ( BaseImporter ) :

   def __init__(self,(rootdir,pkgdir)):
       self.breed = "debian"
       self.ks = "/var/lib/cobbler/kickstarts/sample.seed"
       self.rootdir = rootdir
       self.pkgdir = pkgdir

   def get_release_files(self):
       if not self.get_pkgdir():
           return []
       # search for base-files or base-installer ?
       return glob.glob(os.path.join(self.get_pkgdir(), "main/b/base-files" , "base-files_*"))

   def match_kernelarch_file(self, filename):
       if not filename.endswith("deb"):
           return False
       if filename.startswith("linux-headers-"):
           return True
       return False

   def scan_pkg_filename(self, deb):

       deb = os.path.basename(deb)
       print "- processing deb : %s" % deb

       # get all the tokens and try to guess a version
       accum = []
       tokens = deb.split("_")
       tokens2 = tokens[1].split(".")
       for t2 in tokens2:
          try:
              val = int(t2)
              accum.append(val)
          except:
              pass
       accum.append(0)

       return (None, accum[0], accum[1])

   def set_variance(self, flavor, major, minor, arch):

       dist_names = { '4.0' : "etch" , '5.0' : "lenny" }
       dist_vers = "%s.%s" % ( major , minor )
       os_version = dist_names[dist_vers]

       return os_version , "/var/lib/cobbler/kickstarts/sample.seed"

   def set_install_tree(self, distro, url):
       idx = url.find("://")
       url = url[idx+3:]

       idx = url.find("/")
       distro.ks_meta["hostname"] = url[:idx]
       distro.ks_meta["directory"] = url[idx:]
       if not distro.os_version :
           raise CX(_("OS version is required for debian distros"))
       distro.ks_meta["suite"] = distro.os_version
   
   def process_repos(self, main_importer, distro):

       # Create a disabled repository for the new distro, and the security updates
       #
       # NOTE : We cannot use ks_meta nor os_version because they get fixed at a later stage

       repo = item_repo.Repo(main_importer.config)
       repo.set_breed( "apt" )
       repo.set_arch( distro.arch )
       repo.set_keep_updated( False )
       repo.yumopts["--ignore-release-gpg"] = None
       repo.yumopts["--verbose"] = None
       repo.set_name( distro.name )
       repo.set_os_version( distro.os_version )
       # NOTE : The location of the mirror should come from timezone
       repo.set_mirror( "http://ftp.%s.debian.org/debian/dists/%s" % ( 'us' , '@@suite@@' ) )

       security_repo = item_repo.Repo(main_importer.config)
       security_repo.set_breed( "apt" )
       security_repo.set_arch( distro.arch )
       security_repo.set_keep_updated( False )
       security_repo.yumopts["--ignore-release-gpg"] = None
       security_repo.yumopts["--verbose"] = None
       security_repo.set_name( distro.name + "-security" )
       security_repo.set_os_version( distro.os_version )
       # There are no official mirrors for security updates
       security_repo.set_mirror( "http://security.debian.org/debian-security/dists/%s/updates" % '@@suite@@' )

       print "- Added repos for %s" % distro.name
       repos  = main_importer.config.repos()
       repos.add(repo,save=True)
       repos.add(security_repo,save=True)


class UbuntuImporter ( DebianImporter ) :

   def __init__(self,(rootdir,pkgdir)):
       DebianImporter.__init__(self,(rootdir,pkgdir))
       self.breed = "ubuntu"

   def scan_pkg_filename(self, deb):

       deb = os.path.basename(deb)
       print "- processing deb : %s" % deb

       # get all the tokens and try to guess a version
       accum = []
       tokens = deb.split("_")
       tokens2 = tokens[1].split(".")
       for t2 in tokens2:
          try:
              val = int(t2)
              accum.append(val)
          except:
              pass
       # FIXME : These three lines are the only ones that differ on ubuntu, and actually they filter out the underlying debian version
       if deb.lower().find("ubuntu") != -1:
          accum.pop(0)
          accum.pop(0)
       if not accum:
           accum.extend( tokens2[2:] )
       accum.append(0)

       return (None, accum[0], accum[1])

   def set_variance(self, flavor, major, minor, arch):
  
       # Release names taken from wikipedia
       dist_names = { '4.10':"WartyWarthog", '5.4':"HoaryHedgehog", '5.10':"BreezyBadger", '6.4':"DapperDrake", '6.10':"EdgyEft", '7.4':"FeistyFawn", '7.10':"GutsyGibbon", '8.4':"HardyHeron", '8.10':"IntrepidIbex", '9.4':"JauntyJackalope" }
       dist_vers = "%s.%s" % ( major , minor )
       if not dist_names.has_key( dist_vers ):
           dist_names['4ubuntu2.0'] = "IntrepidIbex"
       os_version = dist_names[dist_vers]

       return os_version , "/var/lib/cobbler/kickstarts/sample.seed"
