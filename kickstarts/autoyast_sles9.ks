<?xml version="1.0"?>
<!DOCTYPE profile>
<profile xmlns="http://www.suse.com/1.0/yast2ns" xmlns:config="http://www.suse.com/1.0/configns">
  <configure>
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
          <filename>post</filename>
          <interpreter>shell</interpreter>
          <location></location>
          <source><![CDATA[#post
# Start final steps
$kickstart_done
# End final steps
]]></source>
        </script>
      </post-scripts>
      <pre-scripts config:type="list">
        <script>
          <filename>pre</filename>
          <interpreter>shell</interpreter>
          <location></location>
          <source><![CDATA[
]]></source>
        </script>
      </pre-scripts>
    </scripts>
    <x11>
      <color_depth config:type="integer">16</color_depth>
      <configure_x11 config:type="boolean">true</configure_x11>
      <display_manager>kdm</display_manager>
      <enable_3d config:type="boolean">true</enable_3d>
      <monitor>
        <display>
          <frequency config:type="integer">60</frequency>
          <height config:type="integer">768</height>
          <width config:type="integer">1024</width>
        </display>
        <monitor_device>1024X768@60HZ</monitor_device>
        <monitor_vendor> LCD</monitor_vendor>
      </monitor>
      <resolution>1024x768</resolution>
      <window_manager>kde</window_manager>
    </x11>
  <ca_mgm>
    </ca_mgm>
    <networking>
      <dns>
        <dhcp_hostname config:type="boolean">false</dhcp_hostname>
        <dhcp_resolv config:type="boolean">false</dhcp_resolv>
        <domain>racemi.com</domain>
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
	<printer>
      <cups_installation config:type="symbol">server</cups_installation>
      <default></default>
      <printcap config:type="list"/>
      <server_hostname></server_hostname>
      <spooler>cups</spooler>
    </printer>
    <sound>
      <configure_detected config:type="boolean">false</configure_detected>
      <modules_conf config:type="list"/>
      <rc_vars/>
      <volume_settings config:type="list"/>
    </sound>
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
<users config:type="list"> 
<user> 
<username>root</username> 
<user_password>$default_password_crypted</user_password> 
<encrypted config:type="boolean">true</encrypted> 
<forename/> 
<surname/> 
</user>
</users>
  </configure>
  <install>
    <general>
      <clock>
        <hwclock>localtime</hwclock>
        <timezone>US/Eastern</timezone>
      </clock>
      <keyboard>
        <keymap>english-us</keymap>
      </keyboard>
      <language>en_US</language>
      <mode>
        <confirm config:type="boolean">true</confirm>
      </mode>
      <mouse>
        <id>probe</id>
      </mouse>
    </general>
    <partitioning config:type="list">
      <drive>
        <use>all</use>
      </drive>
    </partitioning>
    <software>
      <addons config:type="list">
        <addon>auth</addon>
        <addon>X11</addon>
        <addon>YaST2</addon>
        <addon>SuSE-Documentation</addon>
        <addon>Print-Server</addon>
        <addon>Linux-Tools</addon>
        <addon>Kde-Desktop</addon>
        <addon>Basis-Sound</addon>
        <addon>Base-System</addon>
      </addons>
      <base>default</base>
    </software>
  </install>
</profile>
