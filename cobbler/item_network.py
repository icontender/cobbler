"""
A Cobbler repesentation of an IP network.

Copyright 2009, Red Hat, Inc
John Eckersberg <jeckersb@redhat.com>

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

import utils
import item
from cexceptions import *
from utils import _, _IP, _CIDR

class Network(item.Item):

    TYPE_NAME = _("network")
    COLLECTION_TYPE = "network"

    def make_clone(self):
        ds = self.to_datastruct()
        cloned = Network(self.config)
        cloned.from_datastruct(ds)
        return cloned

    def clear(self,is_subobject=False):
        self.name             = None
        self.cidr             = None
        self.address          = None
        self.gateway          = None
        self.broadcast        = None
        self.nameservers      = []
        self.reserved         = []
        self.used_addresses   = {}
        self.free_addresses   = []
        self.comment          = ""

    def from_datastruct(self,seed_data):
        self.name             = self.load_item(seed_data, 'name')
        self.cidr             = _CIDR(self.load_item(seed_data, 'cidr'))
        self.address          = _IP(self.load_item(seed_data, 'address', self.cidr[0]))
        self.gateway          = _IP(self.load_item(seed_data, 'gateway', self.cidr[-2]))
        self.broadcast        = _IP(self.load_item(seed_data, 'broadcast', self.cidr[-1]))
        self.nameservers      = [_IP(i) for i in self.load_item(seed_data, 'nameservers', [])]
        self.reserved         = [_CIDR(c) for c in self.load_item(seed_data, 'reserved', [])]
        self.used_addresses   = self.load_item(seed_data, 'used_addresses', {})
        self.free_addresses   = [_CIDR(c) for c in self.load_item(seed_data, 'free_addresses', [])]
        self.comment          = self.load_item(seed_data, 'comment', '')

        return self

    def set_cidr(self, cidr):
        if self.cidr == None:
            self.free_addresses = [_CIDR(cidr)]
        self.cidr = _CIDR(cidr)

    def set_address(self, address):
        if self.address != None:
            self._add_to_free(address)
        self.address = _IP(address)
        self._remove_from_free(self.address)

    def set_gateway(self, gateway):
        if self.gateway != None:
            self._add_to_free(gateway)
        self.gateway = _IP(gateway)
        self._remove_from_free(self.gateway)

    def set_broadcast(self, broadcast):
        if self.broadcast != None:
            self._add_to_free(broadcast)
        self.broadcast = _IP(broadcast)
        self._remove_from_free(self.broadcast)

    def set_nameservers(self, nameservers):
        old = self.nameservers
        nameservers = [_IP(s.strip()) for s in nameservers.split(',')]
        if old != None:
            for ns in old:
                if ns not in nameservers:
                    self._add_to_free(ns)
        for ns in nameservers:
            if ns not in old:
                self._remove_from_free(ns)
        self.nameservers = nameservers

    def set_reserved(self, reserved):
        pass

    def get_assigned_address(self, system, intf):
        """
        Get the address in the network assigned to an interface of a system.
        """
        try:
            return str(self.used_addresses[(system, intf)])
        except KeyError:
            return None

    def subscribe_system(self, system, intf, ip=None):
        """
        Join a system to the network.  If ip is passed in, try to
        claim that specific address, otherwise just grab the first
        free address.
        """
        if not ip:
            if self.free_address_count() == 0:
                raise CX(_("Network %s has no free addresses" % self.cidr))
            ip = self.free_addresses[0][0]

        self._allocate_address(system, intf, ip)

    def unsubscribe_system(self, system, intf):
        """
        Remove a system from the network.  Allocate it's address back
        into the free pool.
        """
        addr = self.get_assigned_address(system, intf)
        if not addr:
            raise CX(_("Attempting to unsubscribe %s:%s from %s, but not subscribed" % (system, intf, self.name)))

        self._remove_from_used(addr)
        self._add_to_free(addr)

    def _addr_available(self, addr):
        """
        Is addr free in the network?
        """
        for cidr in self.free_addresses:
            if addr in cidr:
                return True
        return False

    def _add_to_free(self, addr, compact=True):
        """
        Add addr to the list of free addresses.  If compact is True,
        then take the list of CIDRs in free_addresses and compact it.
        """
        addr = _IP(addr).cidr()
        self.free_addresses.append(addr)
        if compact:
            self.free_addreses = self._compact(self.free_addresses)

    def _remove_from_free(self, addr):
        """
        Take addr off of the list of free addresses
        """
        self.free_addresses = self._subtract_and_flatten(self.free_addresses, [addr])
        self.free_addresses.sort()

    def _add_to_used(self, system, intf, addr):
        """
        Add system,intf with address to used_addresses.  Make sure no
        entry already exists.
        """
        if (system, intf) in self.used_addresses:
            # should really throw an error if it's already there
            # probably a sign something has gone wrong elsewhere
            raise CX(_("Trying to add %s to used_addresses but is already there!" % i))

        self.used_addresses[(system,intf)] = addr

    def _remove_from_used(self, addr):
        """
        Take addr off of the list of used addresses
        """
        for k,v in self.used_addresses.iteritems():
            if v == addr:
                del(self.used_addresses[k])
                return

    def _allocate_address(self, system, intf, addr):
        """
        Try to allocate addr to system on interface intf.
        """
        if not self._addr_available(addr):
            raise CX(_("Address %s is not available for allocation" % addr))
        self._remove_from_free(addr)
        self._add_to_used(system, intf, addr)

    def _subtract_and_flatten(self, cidr_list, remove_list):
        """
        For each item I in remove_list, find the cidr C in cidr_list
        that contains I.  Perform the subtraction C - I which returns
        a new minimal cidr list not containing I.  Replace C with this
        result, flattened out so we don't get multiple levels of
        lists.
        """
        for item in remove_list:
            for i in range(len(cidr_list)):
                if item in cidr_list[i]:
                    cidr_list += cidr_list[i] - item
                    del(cidr_list[i])
                    break
        return cidr_list

    def _compact(self, cidr_list, sort_first=True):
            """
            Compacts a list of CIDR objects down to a minimal-length list L
            such that the set of IP addresses contained in L is the same as
            the original.

            For example:
            [10.0.0.0/32, 10.0.0.1/32, 10.0.0.2/32, 10.0.0.3/32]
            becomes
            [10.0.0.0/30]
            """
            if len(cidr_list) <= 1:
                return cidr_list

            if sort_first:
                cidr_list.sort()

            did_compact = False
            skip_next = False
            compacted = []
            for i in range(1, len(cidr_list)):
                cur = cidr_list[i]
                prev = cidr_list[i-1]

                if skip_next:
                    skip_next = False
                    continue

                last = prev[-1]
                last += 1
                last = last.cidr()
                if last == cur[0].cidr() and prev.size() == cur.size():
                    compacted.append(CIDR('%s/%d' % (str(prev[0]), prev.prefixlen - 1)))
                    did_compact = True
                    skip_next = True

                if did_compact:
                    return compact(compacted, sort_first=False)
                else:
                    return cidr_list


    def used_address_count(self):
        return len(self.used_addresses)

    def free_address_count(self):
        total = 0
        for item in self.free_addresses:
            total += len(item)
        return total

    def is_valid(self):
        """
	A network is valid if:
          * it has a name and a CIDR
          * it does not overlap another network
	"""
        if self.name is None:
            raise CX(_("name is required"))
        if self.cidr is None:
            raise CX(_("cidr is required"))
        for other in self.config.networks():
            if other.name == self.name:
                continue
            if self.cidr in other.cidr or other.cidr in self.cidr:
                raise CX(_("cidr %s overlaps with network %s (%s)" % (self.cidr, other.name, other.cidr)))
        return True

    def to_datastruct(self):
        def convert_used_addresses(d):
            """
            used_addresses is a bit more involved...
            """
            stringified = {}
            for k,v in d.iteritems():
                stringified[k] = str(v)
            return stringified

        return {
            'name'           : self.name,
            'cidr'           : str(self.cidr),
            'address'        : str(self.address),
            'gateway'        : str(self.gateway),
            'broadcast'      : str(self.broadcast),
            'nameservers'    : [str(i) for i in self.nameservers],
            'reserved'       : [str(i) for i in self.reserved],
            'used_addresses' : convert_used_addresses(self.used_addresses),
            'free_addresses' : [str(i) for i in self.free_addresses],
            'comment'        : self.comment
        }

    def printable(self):
        buf =       _("network          : %s\n") % self.name
        buf = buf + _("CIDR             : %s\n") % self.cidr
        buf = buf + _("gateway          : %s\n") % self.gateway
        buf = buf + _("network address  : %s\n") % self.address
        buf = buf + _("broadcast        : %s\n") % self.broadcast
        buf = buf + _("nameservers      : %s\n") % [str(i) for i in self.nameservers]
        buf = buf + _("reserved         : %s\n") % [str(i) for i in self.reserved]
        buf = buf + _("free addresses   : %s\n") % self.free_address_count()
        buf = buf + _("used addresses   : %s\n") % self.used_address_count()
        buf = buf + _("comment          : %s\n") % self.comment
        return buf

    def get_parent(self):
        """
        currently the Cobbler object space does not support subobjects of this object
        as it is conceptually not useful.
        """
        return None

    def remote_methods(self):
        return {
            'name'           : self.set_name,
            'cidr'           : self.set_cidr,
            'address'        : self.set_address,
            'gateway'        : self.set_gateway,
            'broadcast'      : self.set_broadcast,
            'nameservers'    : self.set_nameservers,
            'reserved'       : self.set_reserved,
            'used_addresses' : self.set_used_addresses,
            'free_addresses' : self.set_free_addresses,
            'comment'        : self.set_comment
        }
