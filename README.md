# WPA Supplicant Configuration over Bluetooth
Configuring the wireless interface on a newly deployed Raspberry Pi typically involves: 1) modifying system files on the Pi's SD card prior to installation, 2) connecting to the Pi via a monitor/keyboard and manually modifying system files, or 3) some other mechanism that requires relatively low-level access to and detailed knowledge of the Linux operating system. On the Raspberry Pi, the wireless network is often managed via changes to the [WPA Supplicant](https://wiki.archlinux.org/title/wpa_supplicant) system file that specifies network connection parameters.

This repository provides server and client applications that configure the WPA Supplicant wireless interface (e.g., wlan0) of Linux-based systems such as the Raspberry Pi using a Bluetooth connection. The **server software** accepts standard WPA Supplicant parameters from the client and applies those parameters to the WPA Supplicant system file on the server device. It then recofigures the interface using those parameters. The **client software** allows the user to customize the wireless interface settings and then apply them to the server device over Blutooth. The user does not have to manually modify the server operating system files or physically attach (cables) to the server device to connect to the wireless network.

This approach benefits product developers who supply the Raspberry Pi or similar Linux-based processing systems as part of their product line as the end user does not have to manually modify system files in order to connect the product to their home wireless network. The developer installs the server software on the Raspberry Pi, and the user installs the client software on their home computer - the user then runs the client software to connect the Raspberry Pi to their wireless network.

## Bluetooth Terminology
Excellent overview of BLE terminilogy provided by this [Adafruit article](https://learn.adafruit.com/introduction-to-bluetooth-low-energy).

**GAP: Generic Access Profile**

Controls connections and advertising in Bluetooth. 

**GATT: Generic ATTribute Profile**

Defines the way that two BLE devices transfer data back and forth using concepts called Services and Characteristics. It makes use of a generic
data protocol called the Attribute Protocol (ATT), which is used to store Services, Characteristics and related data in a simple lookup table
using 16-bit IDs for each entry in the table.

**Peripheral Device**

The peripheral device is known as the GATT Server, which holds the ATT lookup data and service and characteristic definitions.

**Central Device**

The central (main) device is known as the GATT Client (the phone/tablet), which sends requests to the server.

## Bluetooth Specifications

[Specifications and Test Documents List](https://www.bluetooth.com/specifications/specs/)

## Server Application

The server uses the Linux [D-Bus](https://www.freedesktop.org/wiki/Software/dbus/) interprocess communications system to communicate to the
[BlueZ](http://www.bluez.org/) Linux Bluetooth protocol stack. It also uses the Linux [dhcpcd](https://wiki.archlinux.org/title/Dhcpcd)
service to restart the WPA Supplicant wireless interface.

The following sections assume the use of the fictitious `linux` username - customize for your needs.

### Installation

Installation of the server software involves logging into the Raspberry Pi, downloading the install script, and then running the script. When you execute the install script, provide the username under which the server software is to be installed as a command line argument (e.g., `./INSTALL.sh linux`). Also, you must have `root` access in order to install the server software.

Example installation (assuming you are logged into the Raspberry Pi with `root` (sudo) access):

`$ wget https://github.com/lairdrt/wpable/blob/d38285d6c03b02848509ddde6c135667bac13985/INSTALL.sh`

`$ ./INSTALL.sh linux`

Alternatively, you can manually enter the commands in the sections below to install and configure the sever software. You will need to change the default username `linux` to your targeted username within the server files `service-auth.pkla` and `wpable.conf`. This is done for you when you run the provided install script.

The file `INSTALL.sh` executes the commands given in the **Installation**, **File System Permissions**, and **User Authentication** sections.

Under Linux, the server software is installed in: `\etc\wpable`

To install the server software, issue the following commands:

`$ sudo mkdir -p /etc/wpable`

`$ sudo chown linux /etc/wpable`

`$ cd /etc/wpable`

`$ git clone git@github.com:lairdrt/wpable.git temp`

`$ cp temp/server/* .`

`$ rm -f -R temp`

`$ python -m venv venv`

`$ source venv/bin/activate`

`$ pip install -r requirements.txt`

`$ sudo cp wpable.conf /etc/supervisor/conf.d/wpable.conf`

### File System Permissions

The sever application needs write access to the `wpa_supplicant.conf` file, so file permissions need to be changed as follows:

`$ sudo chown linux /etc/wpa_supplicant/wpa_supplicant.conf`

The server also needs access to the `/var/log` directory to write its log file, so permissions need to be set as follows:

`$ sudo touch /var/log/wpable.log`

`$ sudo chown linux /var/log/wpable.log`

### User Authentication

The server application invokes the Linux `systemctl` management tool to restart the `dhcpcd` service that applies changes made to the
`wpa_supplicnat.conf` file. In order to be able to invoke `systemctl` (which runs under the `systemd` system manager daemon) from within a
Python script, the user under which the server software executes must be authenticated by the system Policy Kit Local Authority manager (`polkit`).

A local authority file (`.pkla`) must be copied to the appropriate location as the `root` user:

`$ sudo cp /etc/wpable/service-auth.pkla /etc/polkit-1/localauthority/50-local.d`

Refer to the following for more information:

https://www.freedesktop.org/software/polkit/docs/0.105/pklocalauthority.8.html

https://unix.stackexchange.com/questions/650826/why-is-this-error-interactive-authentication-required-popping-up

https://unix.stackexchange.com/questions/407967/polkit-rules-not-recognized-raspbian-stretch

## Client Application

The client software uses the [SimpleBLE library](https://simpleble.readthedocs.io/en/latest/index.html) as a cross-platform solution. General build instructions are [here](https://simpleble.readthedocs.io/en/latest/simpleble/usage.html), but they are not complete. The library source files can be downloaded from GitHub [here](https://github.com/OpenBluetoothToolbox/SimpleBLE).

The client was developed under Microsoft Visual Studio Community 2022 (64-bit) - Current Version 17.4.3 as a "Project for a single page C++/WinRT Universal Windows Platform (UWP) app with no predefined layout".

### Windows 10

The SimpleBle library requires:

1. [Microsoft Visual Studio Community 2022](https://visualstudio.microsoft.com/vs/community/)
2. [Microsoft Windows SDK Version 10.0.19041.0 "or higher" Windows 10 SDK](https://developer.microsoft.com/en-us/windows/downloads/sdk-archive/)
3. [CMake version 3.25](https://cmake.org/download/)

**Note:**

Windows SDK versions 10.0.22621.755 and 10.0.22000.194 target Windows 11 and both cause C++/WinRT version mismatch errors during link of MS Visual Studio Community 2022 solution build.

To build the SimpleBLE library under Windows (assuming the SimpleBLE software has been downloaded into the directory `SimpleBLE`), issue the following commands using a command shell that has **System Administrator** privileges:

`C:\> cd \SimpleBLE\simpleble`

`C:\SimpleBLE\simpleble> mkdir build`

`C:\SimpleBLE\simpleble> cd build`

`C:\SimpleBLE\simpleble\build> cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=17 -DCMAKE_SYSTEM_VERSION=10.0.19041.0`

`C:\SimpleBLE\simpleble\build> cmake --build . -j7 --config Release`

`C:\SimpleBLE\simpleble\build> cmake --install . --config Release`

The `install` target does not copy the libraries to the intended directory, so you need to issue the following commands to do so:

`C:\SimpleBLE\simpleble\build> mkdir C:\"Program Files (x86)"\simpleble\lib\Release`

`C:\SimpleBLE\simpleble\build> copy lib\Release\*.lib C:\"Program Files (x86)"\simpleble\lib\Release\*.lib`

### In Microsoft Visual Studio:

1. Add the include directory for the SimpleBLE library:

    `Project Solution > Properties > Configuration Properties > C/C++ > General > Additional Include Directories`

2. Add the library directory for the SimpleBLE library:

    `Project Solution > Properties > Configuration Properties > Linker > General > Additional Library Directories`

3. Add the library to the project solution:

    `Project Solution > Properties > Configuration Properties > Linker > Input > Additional Dependencies`

4. Set target Windows SDK version:
 
    `Project Solution > Properties > Configuration Properties > General > Windows SDK Version`
