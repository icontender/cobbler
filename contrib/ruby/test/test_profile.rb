#
#  test_profile.rb - Tests the Profile class.
# 
# Copyright (C) 2008 Red Hat, Inc.
# Written by Darryl L. Pierce <dpierce@redhat.com>
#
# This file is part of rubygem-cobbler.
#
# rubygem-cobbleris free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published 
# by the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# rubygem-cobbler is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with rubygem-cobbler.  If not, see <http://www.gnu.org/licenses/>.
#
 
$:.unshift File.join(File.dirname(__FILE__),'..','lib')

require 'test/unit'
require 'flexmock/test_unit'
require 'cobbler'

module Cobbler
  class TestProfile < Test::Unit::TestCase
    def setup
      @connection = flexmock('connection')
      Profile.connection = @connection
      Profile.hostname   = "localhost"
      
      @profiles = Array.new
      @profiles << {
        'profile'        => 'Fedora-9-i386',
        'distro'         => 'Fedora-9-i386',
        'dhcp tag'       => 'default',
        'kernel options' => {},
        'kickstart'      => '/etc/cobbler/sample_end.ks',
        'ks metadata'    => {},
        'owners'         => ['admin'],
        'repos'          => [],
        'server'         => '<<inherit>>',
        'virt auto boot' => 0,
        'virt bridge'    => 'xenbr0',
        'virt cpus'      => '1',
        'virt file size' => '5',
        'virt path'      => '',
        'virt ram'       => '512',
        'virt type'      => 'xenpv',
      }
      
      @profiles << {
        'profile'        => 'Fedora-9-x86_64',
        'distro'         => 'Fedora-9-x86_64',
        'dhcp tag'       => 'default',
        'kernel options' => {},
        'kickstart'      => '/etc/cobbler/sample_end.ks',
        'ks metadata'    => {},
        'owners'         => ['admin'],
        'repos'          => [],
        'server'         => '<<inherit>>',
        'virt auto boot' => 0,
        'virt bridge'    => 'xenbr0',
        'virt cpus'      => '1',
        'virt file size' => '5',
        'virt path'      => '',
        'virt ram'       => '512',
        'virt type'      => 'xenpv',
      }
      
    end

    # Ensures that an attempt to find all of a profile works as expected.
    #
    def test_find
      @connection.should_receive(:call).with('get_profiles').once.returns(@profiles)

      result = Profile.find

      assert result, 'Expected a result set.'
      assert_equal 2, result.size, 'Did not receive the right number of results'
    end
  end
end
