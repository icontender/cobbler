"""
Profile CLI module.

Copyright 2007-2008, Red Hat, Inc
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

import distutils.sysconfig
import sys

plib = distutils.sysconfig.get_python_lib()
mod_path="%s/cobbler" % plib
sys.path.insert(0, mod_path)

from utils import _
import cobbler.commands as commands
import cexceptions


class ProfileFunction(commands.CobblerFunction):

    def help_me(self):
        return commands.HELP_FORMAT % ("cobbler profile","<add|copy|edit|find|getks|list|rename|remove|report> [ARGS]")

    def command_name(self):
        return "profile"

    def subcommands(self):
        return ["add","copy","dumpvars","edit","find","getks","list","remove","rename","report"]

    def add_options(self, p, args):
            
        if not self.matches_args(args,["dumpvars","remove","report","getks","list"]):
            p.add_option("--comment",  dest="comment",  help="user field")

        if self.matches_args(args,["add"]):
            p.add_option("--clobber", dest="clobber", help="allow add to overwrite existing objects", action="store_true")


        if not self.matches_args(args,["dumpvars","remove","report","getks","list"]):

            p.add_option("--distro",           dest="distro",    help="ex: 'RHEL-5-i386' (REQUIRED)")
            p.add_option("--dhcp-tag",         dest="dhcp_tag",  help="for use in advanced DHCP configuration")
            p.add_option("--enable-menu", dest="enable_menu", help="yes/no. When yes, adds profile to default PXE menu")
            p.add_option("--inherit",          dest="inherit",   help="inherit from this profile name, defaults to no")
            if not self.matches_args(args,["find"]):
                p.add_option("--in-place",action="store_true", dest="inplace", default=False, help="edit items in kopts, kopts_post or ksmeta without clearing the other items")
            p.add_option("--kickstart",        dest="kickstart", help="absolute path to kickstart template (RECOMMENDED)")
            p.add_option("--ksmeta",           dest="ksmeta",    help="ex: 'blippy=7'")
            p.add_option("--kopts",            dest="kopts",     help="ex: 'noipv6'")
            p.add_option("--kopts-post",       dest="kopts_post",help="ex: 'clocksource=pit'")
            p.add_option("--mgmt-classes", dest="mgmt_classes",  help="list of config management classes (for Puppet, etc)")


        p.add_option("--name",   dest="name",  help="a name for the profile (REQUIRED)")

        if not self.matches_args(args,["dumpvars","remove","report","getks","list"]):

            p.add_option("--name-servers", dest="name_servers",  help="name servers for static setups")
            p.add_option("--name-servers-search", dest="name_servers_search",  help="name servers search path for static setups")

        if "copy" in args or "rename" in args:
            p.add_option("--newname", dest="newname")

        if not self.matches_args(args,["dumpvars","find","remove","report","getks","list"]):
            p.add_option("--no-sync",     action="store_true", dest="nosync", help="suppress sync for speed")
        if not self.matches_args(args,["dumpvars","find","report","getks","list"]):
            p.add_option("--no-triggers", action="store_true", dest="notriggers", help="suppress trigger execution")
        if not self.matches_args(args,["dumpvars","report","getks","list"]):
            p.add_option("--owners", dest="owners", help="specify owners for authz_ownership module")

        if self.matches_args(args,["remove"]):
            p.add_option("--recursive", action="store_true", dest="recursive", help="also delete child objects")

        if not self.matches_args(args,["dumpvars","remove","report","getks","list"]):
            p.add_option("--redhat-management-key", dest="redhat_management_key", help="authentication token for RHN/Spacewalk/Satellite")
            p.add_option("--redhat-management-server", dest="redhat_management_server", help="RHN/Spacewalk/Satellite server")
            p.add_option("--repos",            dest="repos", help="names of cobbler repos")
            p.add_option("--server",           dest="server_override", help="overrides value in settings file")
            p.add_option("--template-files",   dest="template_files", help="specify files to be generated from templates during a sync")
            p.add_option("--virt-auto-boot",   dest="virt_auto_boot", help="auto boot this VM with host?")
            p.add_option("--virt-bridge",      dest="virt_bridge", help="ex: 'virbr0'")
            p.add_option("--virt-cpus",        dest="virt_cpus", help="integer (default: 1)")
            p.add_option("--virt-file-size",   dest="virt_file_size", help="size in GB")
            p.add_option("--virt-path",        dest="virt_path", help="path, partition, or volume")
            p.add_option("--virt-ram",         dest="virt_ram", help="size in MB")
            p.add_option("--virt-type",        dest="virt_type", help="ex: 'xenpv', 'qemu'")

    def run(self):

        if self.args and "find" in self.args:
            items = self.api.find_profile(return_list=True, no_errors=True, **self.options.__dict__)
            for x in items:
                print x.name
            return True

        if self.matches_args(self.args,["report","getks","list","remove","dumpvars"]) or not self.options.inherit:
            obj = self.object_manipulator_start(self.api.new_profile,self.api.profiles,subobject=False)
        else:
            obj = self.object_manipulator_start(self.api.new_profile,self.api.profiles,subobject=True)

        if obj is None:
            return True

        if not self.matches_args(self.args,["dumpvars","getks"]):
            if self.options.comment is not None:         
                obj.set_comment(self.options.comment)
            if self.options.inherit is not None:         
                obj.set_parent(self.options.inherit)
            if self.options.distro is not None:          
                obj.set_distro(self.options.distro)
            if self.options.enable_menu is not None:
                obj.set_enable_menu(self.options.enable_menu)
            if self.options.kickstart is not None:       
                obj.set_kickstart(self.options.kickstart)
            if self.options.kopts is not None:           
                obj.set_kernel_options(self.options.kopts,self.options.inplace)
            if self.options.kopts_post is not None:      
                obj.set_kernel_options_post(self.options.kopts_post,self.options.inplace)
            if self.options.ksmeta is not None:          
                obj.set_ksmeta(self.options.ksmeta,self.options.inplace)
            if self.options.virt_auto_boot is not None:
                obj.set_virt_auto_boot(self.options.virt_auto_boot)
            if self.options.virt_file_size is not None:  
                obj.set_virt_file_size(self.options.virt_file_size)
            if self.options.virt_ram is not None:        
                obj.set_virt_ram(self.options.virt_ram)
            if self.options.virt_bridge is not None:     
                obj.set_virt_bridge(self.options.virt_bridge)
            if self.options.virt_type is not None:       
                obj.set_virt_type(self.options.virt_type)
            if self.options.virt_cpus is not None:       
                obj.set_virt_cpus(self.options.virt_cpus)
            if self.options.repos is not None:           
                obj.set_repos(self.options.repos)
            if self.options.virt_path is not None:       
                obj.set_virt_path(self.options.virt_path)
            if self.options.dhcp_tag is not None:        
                obj.set_dhcp_tag(self.options.dhcp_tag)
            if self.options.server_override is not None: 
                obj.set_server(self.options.server_overide)

            if self.options.owners is not None:          
                obj.set_owners(self.options.owners)
            if self.options.mgmt_classes is not None:    
                obj.set_mgmt_classes(self.options.mgmt_classes)
            if self.options.template_files is not None:  
                obj.set_template_files(self.options.template_files,self.options.inplace)
            if self.options.name_servers is not None:    
                obj.set_name_servers(self.options.name_servers)
            if self.options.name_servers_search is not None:
                obj.set_name_servers_search(self.options.name_servers_search)
            if self.options.redhat_management_key is not None:
                obj.set_redhat_management_key(self.options.redhat_management_key)
            if self.options.redhat_management_server is not None:
                obj.set_redhat_management_server(self.options.redhat_management_server)


        return self.object_manipulator_finish(obj, self.api.profiles, self.options)



########################################################
# MODULE HOOKS

def register():
    """
    The mandatory cobbler module registration hook.
    """
    return "cli"

def cli_functions(api):
    return [
       ProfileFunction(api)
    ]


