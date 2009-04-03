<?xml version="1.0"?>
<!DOCTYPE profile>
<profile xmlns="http://www.suse.com/1.0/yast2ns" xmlns:config="http://www.suse.com/1.0/configns">
  <add-on/>
  <ca_mgm>
    <CAName>YaST_Default_CA</CAName>
    <ca_commonName>$hostname</ca_commonName>
    <country>US</country>
    <importCertificate config:type="boolean">false</importCertificate>
    <locality>USA</locality>
    <organisation>Organization</organisation>
    <organisationUnit>OU</organisationUnit>
    <password>$default_password_crypted</password>
    <server_email>email@email.com</server_email>
    <state>GA</state>
    <takeLocalServerName config:type="boolean">true</takeLocalServerName>
  </ca_mgm>
  <firewall>
    <enable_firewall config:type="boolean">false</enable_firewall>
    <start_firewall config:type="boolean">false</start_firewall>
  </firewall>
  <general>
    <mode>
      <confirm config:type="boolean">false</confirm>
      <halt config:type="boolean">false</halt>
      <second_stage config:type="boolean">true</second_stage>
    </mode>
    <mouse>
      <id>probe</id>
    </mouse>
    <signature-handling>
      <accept_file_without_checksum config:type="boolean">true</accept_file_without_checksum>
      <accept_non_trusted_gpg_key config:type="boolean">true</accept_non_trusted_gpg_key>
      <accept_unknown_gpg_key config:type="boolean">true</accept_unknown_gpg_key>
      <accept_unsigned_file config:type="boolean">true</accept_unsigned_file>
      <accept_verification_failed config:type="boolean">false</accept_verification_failed>
      <import_gpg_key config:type="boolean">true</import_gpg_key>
    </signature-handling>
  </general>
  <users>
    <user>
      <encrypted config:type="boolean">true</encrypted>
      <password_settings />
      <gid>0</gid>
      <home>/root</home>
      <shell>/bin/bash</shell>
      <uid>0</uid>
      <user_password>$default_password_crypted</user_password>
      <username>root</username>
      <fullname>root</fullname>
    </user>
   </users>
   <iscsi-client>
     <version>1.0</version>
  </iscsi-client>
  <keyboard>
    <keymap>english-us</keymap>
  </keyboard>
  <language>
    <language>en_US</language>
    <languages>en_US</languages>
  </language>
  <partitioning config:type="list">
    <drive>
      <use>all</use>
    </drive>
  </partitioning>
  <runlevel>
    <default>5</default>
  </runlevel>
  <scripts>
<chroot-scripts config:type="list">
        <script>
          <chrooted config:type="boolean">false</chrooted>
          <filename>chroot</filename>
          <interpreter>shell</interpreter>
          <location></location>
          <source><![CDATA[#chroot
# Start final steps
$kickstart_done
# End final steps
]]></source>
        </script>
      </chroot-scripts>

    <post-scripts config:type="list">
      <script>
        <debug config:type="boolean">true</debug>
        <feedback config:type="boolean">false</feedback>
        <filename>post</filename>
        <interpreter>shell</interpreter>
        <location></location>
        <network_needed config:type="boolean">false</network_needed>
        <source><![CDATA[#post

# Begin final steps
$kickstart_done
# End final steps]]></source>
      </script>
    </post-scripts>
    <pre-scripts config:type="list">
      <script>
        <debug config:type="boolean">false</debug>
        <feedback config:type="boolean">false</feedback>
        <filename>pre</filename>
        <interpreter>shell</interpreter>
        <location></location>
        <source><![CDATA[#pre
# Begin final steps
$kickstart_done
# End final steps]]></source>
      </script>
    </pre-scripts>
  </scripts>
  <security>
      <console_shutdown>reboot</console_shutdown>
      <cracklib_dict_path>/usr/lib/cracklib_dict</cracklib_dict_path>
      <cwd_in_root_path>yes</cwd_in_root_path>
      <cwd_in_user_path>yes</cwd_in_user_path>
      <displaymanager_remote_access>no</displaymanager_remote_access>
      <enable_sysrq>no</enable_sysrq>
      <fail_delay>1</fail_delay>
      <faillog_enab>yes</faillog_enab>
      <gid_max>60000</gid_max>
      <gid_min>1000</gid_min>
      <kdm_shutdown>all</kdm_shutdown>
      <lastlog_enab>yes</lastlog_enab>
      <obscure_checks_enab>no</obscure_checks_enab>
      <pass_max_days>99999</pass_max_days>
      <pass_max_len>8</pass_max_len>
      <pass_min_days>0</pass_min_days>
      <pass_min_len>5</pass_min_len>
      <pass_warn_age>7</pass_warn_age>
      <passwd_encryption>md5</passwd_encryption>
      <passwd_use_cracklib>no</passwd_use_cracklib>
      <permission_security>easy</permission_security>
      <run_updatedb_as>root</run_updatedb_as>
      <system_gid_max>499</system_gid_max>
      <system_gid_min>100</system_gid_min>
      <system_uid_max>499</system_uid_max>
      <system_uid_min>100</system_uid_min>
      <uid_max>60000</uid_max>
      <uid_min>1000</uid_min>
      <useradd_cmd>/usr/sbin/useradd.local</useradd_cmd>
      <userdel_postcmd>/usr/sbin/userdel-post.local</userdel_postcmd>
      <userdel_precmd>/usr/sbin/userdel-pre.local</userdel_precmd>
    </security>
  <software>
    <patterns config:type="list">
      <pattern>ccb</pattern>
      <pattern>base</pattern>
      
    </patterns>
  </software>
  <timezone>
    <hwclock>UTC</hwclock>
    <timezone>US/Eastern</timezone>
  </timezone>
 <networking>
      <dns>
        <dhcp_hostname config:type="boolean">false</dhcp_hostname>
        <dhcp_resolv config:type="boolean">false</dhcp_resolv>
        <domain></domain>
        <hostname>$hostname</hostname>
      </dns>
      <interfaces config:type="list">
        <interface>
          <bootproto>dhcp</bootproto>
          <device>eth0</device>
          <startmode>onboot</startmode>
        </interface>
      </interfaces>
      <modules config:type="list">
        <module_entry>
          <device>dhcp</device>
          <module></module>
          <options></options>
        </module_entry>
      </modules>
      <routing>
        <ip_forward config:type="boolean">false</ip_forward>
      </routing>
    </networking>
  <x11>
    <color_depth config:type="integer">24</color_depth>
    <display_manager>gdm</display_manager>
    <enable_3d config:type="boolean">true</enable_3d>
    <monitor>
      <display>
        <max_hsync config:type="integer">60</max_hsync>
        <max_vsync config:type="integer">60</max_vsync>
        <min_hsync config:type="integer">31</min_hsync>
        <min_vsync config:type="integer">30</min_vsync>
      </display>
      <monitor_device>1024X768@60HZ</monitor_device>
      <monitor_vendor>--> LCD</monitor_vendor>
    </monitor>
    <resolution>1024x768 (XGA)</resolution>
    <window_manager>gnome</window_manager>
  </x11>
</profile>
