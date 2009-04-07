"""
Command line handling for Cobbler.

Copyright 2008, Red Hat, Inc
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

import optparse
from cexceptions import *
from utils import _
import sys
import api

HELP_FORMAT = "%-20s%s"

#=============================================================

class FunctionLoader:

    """
    The F'n Loader controls processing of cobbler commands.
    """

    def __init__(self, api):
        """
        When constructed the loader has no functions.
        """
        self.api = api
        self.functions = {}

    def add_func(self, obj):
        """
        Adds a CobblerFunction instance to the loader.
        """
        self.functions[obj.command_name()] = obj

    def run(self, args):
        """
        Runs a command line sequence through the loader.
        """

        args = self.old_school_remap(args)

        # if no args given, show all loaded fns
        if len(args) == 1:
            return self.show_options()

        called_name = args[1].lower()

        # if -v or --version, make it work
        if called_name in [ "--version", "-v" ]:
           called_name = "version"
           args = [ "/usr/bin/cobbler", "version" ]


        # also show avail options if command name is bogus
        if len(args) == 2 and not called_name in self.functions.keys():
            if "--helpbash" in args:
                return self.show_options_bashcompletion()
            else:
                return self.show_options()

        try:
            fn = self.functions[called_name]
        except:
            return self.show_options()

        subs = fn.subcommands()

        # three cases to show subcommands:
        # (A):  cobbler profile 
        # (B):  cobbler profile --help
        if len(subs) != 0:
            problem = False
            if (len(args) == 2):
                problem = True
                starter = args[-1]
            if (("-h" in args or "--help" in args) and (len(args) ==  3)):
                problem = True
                starter = args[-2]
            elif len(args) >= 3:
                ignore_it = False
                for x in args[2:]:
                    if x.startswith("--"):
                        ignore_it = True
                    if not x.startswith("-") and x not in subs and not ignore_it:
                        problem = True
                        starter = args[1]
            if problem:
                print "usage:"
                print "======"
                for x in subs:
                    print "cobbler %s %s" % (starter, x)
                sys.exit(1)


        # some functions require args, if none given, show subcommands
        #if len(args) == 2:
        #    no_args_rc = fn.no_args_handler()
        #    if no_args_rc:
        #        return True

        # finally let the object parse its own args
        loaded_ok = fn.parse_args(args)
        if not loaded_ok:
            raise CX(_("Invalid arguments"))
        return fn.run()

    def old_school_remap(self,args): 
        """
        Replaces commands with common synonyms that should also work
     
        Also maps commands like:
             # cobbler system report foo to cobbler report --name=foo
        to:
             # cobblerr system report --name=foo

        for backwards compat and usability reasons
        """

        # to do:  handle synonyms
        for ct in range(0,len(args)):
           args[ct] = args[ct]
           if args[ct].startswith("-"):
               # stop synonym mapping after first option
               break
           # lowercase all args
           args[ct] = args[ct].lower()
           # delete means remove
           # are there any other common synonyms?
           if args[ct] == "delete":
               args[ct] = "remove" 

        # special handling for reports follows:
        if not "report" in args:
            return args
        ok = False
        for x in ["distro","profile","system","repo","image"]:
            if x in args:
                ok = True
        if not ok:
            return args
        idx = args.index("report")
        if idx + 1 < len(args):
           name = args[idx+1]
           if name.find("--name") == -1:
               args[idx+1] = "--name=%s" % name
        return args
       
    def show_options(self):
        """
        Prints out all loaded functions.
        """

        print "commands:  (use --help on a subcommand for usage)"
        print "========"

        names = self.functions.keys()
        names.sort()

        for name in names:
            help = self.functions[name].help_me()
            if help != "":
                print help

    def show_options_bashcompletion(self):
        """
        Prints out all loaded functions in an easily parseable form for
        bash-completion
        """
        names = self.functions.keys()
        names.sort()
        print ' '.join(names)

#=============================================================

class CobblerFunction:

    def __init__(self,api):
        """
        Constructor requires a Cobbler API handle.
        """
        self.api = api
        self.args = []

    def command_name(self):
        """
        The name of the command, as to be entered by users.
        """
        return "unspecified"

    def subcommands(self):
        """
        The names of any subcommands, such as "add", "edit", etc
        """
        return [ ]

    def run(self):
        """
        Called after arguments are parsed.  Return True for success.
        """
        return True

    def add_options(self, parser, args):
        """
        Used by subclasses to add options.  See subclasses for examples.
        """
        pass

    def helpbash(self, parser, args, print_options = True, print_subs = False):
        """
        Print out the arguments in an easily parseable format
        """
        # We only want to print either the subcommands available or the
        # options, but not both
        option_list = []
        if print_subs:
            for sub in self.subcommands():
                option_list.append(sub.__str__())
        elif print_options:
            for opt in parser.option_list:
                option_list.extend(opt.__str__().split('/'))
        print ' '.join(option_list)

    def parse_args(self,args):
        """
        Processes arguments, called prior to run ... do not override.
        """

        accum = ""
        for x in args[1:]:
            if not x.startswith("-"):
                accum = accum + "%s " % x
            else:
                break
        p = optparse.OptionParser(usage="cobbler %s [ARGS]" % accum)
        self.add_options(p, args)
        subs = self.subcommands()
        if len(subs) > 0:
            count = 0
            for x in subs:
                if x in args:
                    count = count + 1               
            if count != 1:
                print "usage:"
                print "======"
                for x in subs: 
                    print "cobbler %s %s [ARGS]" % (self.command_name(), x)
                return True
        (self.options, self.args) = p.parse_args(args)
        return True

    def object_manipulator_start(self,new_fn,collect_fn,subobject=False):
        """
        Boilerplate for objects that offer add/edit/delete/remove/copy functionality.
        """

        if "dumpvars" in self.args:
            if not self.options.name:
                raise CX(_("name is required"))
            obj = collect_fn().find(self.options.name)
            if obj is None:
                raise CX(_("object not found")) 
            return obj

        if "poweron" in self.args:
            obj = collect_fn().find(self.options.name)
            if obj is None:
                raise CX(_("object not found"))
            self.api.power_on(obj,self.options.power_user,self.options.power_pass)
            return None

        if "poweroff" in self.args:
            obj = collect_fn().find(self.options.name)
            if obj is None:
                raise CX(_("object not found"))
            self.api.power_off(obj,self.options.power_user,self.options.power_pass)
            return None

        if "reboot" in self.args:
            obj = collect_fn().find(self.options.name)
            if obj is None:
                raise CX(_("object not found"))
            self.api.reboot(obj,self.options.power_user,self.options.power_pass)
            return None

        if "deploy" in self.args:
            obj = collect_fn().find(self.options.name)
            if obj is None:
                raise CX(_("object not found"))
            if self.options.virt_host == '':
                virt_host = None
            else:
                virt_host = self.options.virt_host

            if self.options.virt_group == '':
                virt_group = None
            else:
                virt_group = self.options.virt_group
            self.api.deploy(obj,virt_host=virt_host,virt_group=virt_group)

        if "remove" in self.args:
            recursive = False
            # only applies to distros/profiles and is not supported elsewhere
            if hasattr(self.options, "recursive"):
                recursive = self.options.recursive
            if not self.options.name:
                raise CX(_("name is required"))
            if not recursive:
                collect_fn().remove(self.options.name,with_delete=True,recursive=False)
            else:
                collect_fn().remove(self.options.name,with_delete=True,recursive=True)
            return None # signal that we want no further processing on the object

        if "list" in self.args:
            self.list_list(collect_fn())
            return None

        if "report" in self.args:
            if self.options.name is None:
                return self.api.report(report_what = self.args[1], report_name = None, \
                               report_type = 'text', report_fields = 'all')
            else:
                return self.api.report(report_what = self.args[1], report_name = self.options.name, \
                                report_type = 'text', report_fields = 'all')

        if "getks" in self.args:
            if not self.options.name:
                raise CX(_("name is required"))
            obj = collect_fn().find(self.options.name)
            if obj is None:
                raise CX(_("object not found")) 
            return obj

        if "deploy" in self.args:
            if not self.options.name:
                raise CX(_("name is required"))
            obj = collect_fn().find(self.options.name)
            if obj is None:
                raise CX(_("object not found"))
            if obj.virt_host == '' or not self.options.virt_host or not self.options.virt_group:
                raise CX(_("No virtual host to deploy to"))
            return obj

        try:
            # catch some invalid executions of the CLI
            getattr(self, "options")
        except:
            sys.exit(1)

        if not self.options.name:
            raise CX(_("name is required"))

        if "add" in self.args:
            obj = new_fn(is_subobject=subobject)
        else:
            if "delete" in self.args:
                collect_fn().remove(self.options.name, with_delete=True)
                return None
            obj = collect_fn().find(self.options.name)
            if obj is None:
                raise CX(_("object named (%s) not found") % self.options.name)

        if not "copy" in self.args and not "rename" in self.args and self.options.name:
            obj.set_name(self.options.name)

        return obj

    def object_manipulator_finish(self,obj,collect_fn, options):
        """
        Boilerplate for objects that offer add/edit/delete/remove/copy functionality.
        """

        if "dumpvars" in self.args:
            print obj.dump_vars(True)
            return True

        if "getks" in self.args:
            ba=api.BootAPI()
            if "system" in self.args:
                rc = ba.generate_kickstart(None, self.options.name)
            if "profile" in self.args:
                rc = ba.generate_kickstart(self.options.name, None)
            if rc is None:
                print "kickstart is not template based"
            else:
                print rc    
            return True

        clobber = False
        if "add" in self.args:
            clobber = options.clobber

        if "copy" in self.args:
            if self.options.newname:
                # FIXME: this should just use the copy function!
                if obj.COLLECTION_TYPE == "distro":
                   return self.api.copy_distro(obj, self.options.newname)
                if obj.COLLECTION_TYPE == "profile":
                   return self.api.copy_profile(obj, self.options.newname)
                if obj.COLLECTION_TYPE == "system":
                   return self.api.copy_system(obj, self.options.newname)
                if obj.COLLECTION_TYPE == "repo":
                   return self.api.copy_repo(obj, self.options.newname)
                if obj.COLLECTION_TYPE == "image":
                   return self.api.copy_image(obj, self.options.newname)
                raise CX(_("internal error, don't know how to copy"))
            else:
                raise CX(_("--newname is required"))

        opt_sync     = not options.nosync
        opt_triggers = not options.notriggers

        # ** WARNING: COMPLICATED **
        # what operation we call depends on what type of object we are editing
        # and what the operation is.  The details behind this is that the
        # add operation has special semantics around adding objects that might
        # clobber other objects, and we don't want that to happen.  Edit
        # does not have to check for named clobbering but still needs
        # to check for IP/MAC clobbering in some scenarios (FIXME).
        # this is all enforced by collections.py though we need to make
        # the apppropriate call to add to invoke the safety code in the right
        # places -- and not in places where the safety code will generate
        # errors under legit circumstances.

        if not ("rename" in self.args):
            if "add" in self.args:
               if obj.COLLECTION_TYPE == "system":
                   # duplicate names and netinfo are both bad.
                   if not clobber:
                       rc = collect_fn().add(obj, save=True, with_sync=opt_sync, with_triggers=opt_triggers, check_for_duplicate_names=True, check_for_duplicate_netinfo=True)
                   else:
                       rc = collect_fn().add(obj, save=True, with_sync=opt_sync, with_triggers=opt_triggers, check_for_duplicate_names=False, check_for_duplicate_netinfo=True)
               else:
                   # duplicate names are bad
                   if not clobber:
                       rc = collect_fn().add(obj, save=True, with_sync=opt_sync, with_triggers=opt_triggers, check_for_duplicate_names=True, check_for_duplicate_netinfo=False)
                   else:
                       rc = collect_fn().add(obj, save=True, with_sync=opt_sync, with_triggers=opt_triggers, check_for_duplicate_names=False, check_for_duplicate_netinfo=False)
            else:
               check_dup = False
               if not "copy" in self.args:
                   check_dup = True 
               rc = collect_fn().add(obj, save=True, with_sync=opt_sync, with_triggers=opt_triggers, check_for_duplicate_netinfo=check_dup)

        else:
            # we are renaming here, so duplicate netinfo checks also
            # need to be made.(FIXME)
            rc = collect_fn().rename(obj, self.options.newname, with_triggers=opt_triggers)

        return rc

    def list_tree(self,collection,level):
        """
        Print cobbler object tree as a, well, tree.
        """

        def sorter(a,b):
            return cmp(a.name,b.name)

        collection2 = []
        for c in collection:
            collection2.append(c)
        collection2.sort(sorter)

        for item in collection2:
            print _("%(indent)s%(type)s %(name)s") % {
                "indent" : "   " * level,
                "type"   : item.TYPE_NAME,
                "name"   : item.name
            }
            kids = item.get_children()
            if kids is not None and len(kids) > 0:
                self.list_tree(kids,level+1)

    def list_list(self, collection):
        """
        List all objects of a certain type.
        """
        names = [ x.name for x in collection]
        names.sort() # sorted() is 2.4 only
        for name in names:
           str = _("%(name)s") % { "name" : name }
           print str
        return True

    def matches_args(self, args, list_of):
        """
        Used to simplify some code around which arguments to add when.
        """
        for x in args:
            if x in list_of:
                return True
        return False


