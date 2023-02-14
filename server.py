#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later

# Adapted from Bluez, PunchThrough:

# bluez/test/example-gatt-server
# https://github.com/bluez/bluez/blob/9be85f867856195e16c9b94b605f65f6389eda33/test/example-gatt-server

# bluez/test/simple-agent
# https://github.com/bluez/bluez/blob/9be85f867856195e16c9b94b605f65f6389eda33/test/simple-agent

# bluez/test/example-advertisement
# https://github.com/bluez/bluez/blob/9be85f867856195e16c9b94b605f65f6389eda33/test/example-advertisement

# https://punchthrough.com/creating-a-ble-peripheral-with-bluez/
# https://github.com/PunchThrough/espresso-ble

# Other refs:

# https://www.uuidgenerator.net/
# https://scapy.readthedocs.io/en/latest/routing.html

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
import array
import json
import logging
import subprocess
import time

from scapy.all import get_if_hwaddr
from gi.repository import GLib, GObject

mainloop = GLib.MainLoop()

logger = logging.getLogger(__name__)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logHandler = logging.StreamHandler()
filelogHandler = logging.FileHandler("/var/log/wpable.log")

logHandler.setFormatter(formatter)
filelogHandler.setFormatter(formatter)

logger.addHandler(logHandler)
logger.addHandler(filelogHandler)

logger.setLevel(logging.INFO)

AGENT_PATH = "/org/bluez/wpable/agent"

DEFAULT_WLAN_IFACE = "wlan0"
WLAN_IFACE_BT_NAME = "rpi-vctrl"

DBUS_OM_IFACE                 = 'org.freedesktop.DBus.ObjectManager'
DBUS_PROP_IFACE               = 'org.freedesktop.DBus.Properties'

BLUEZ_SERVICE_NAME            = 'org.bluez'

AGENT_IFACE                   = "org.bluez.Agent1"

GATT_MANAGER_IFACE            = 'org.bluez.GattManager1'
GATT_SERVICE_IFACE            = 'org.bluez.GattService1'
GATT_CHRC_IFACE               = 'org.bluez.GattCharacteristic1'
GATT_DESC_IFACE               = 'org.bluez.GattDescriptor1'

LE_ADVERTISEMENT_IFACE        = 'org.bluez.LEAdvertisement1'
LE_ADVERTISING_MANAGER_IFACE  = 'org.bluez.LEAdvertisingManager1'


class InvalidArgsException(dbus.exceptions.DBusException):
    _dbus_error_name = 'org.freedesktop.DBus.Error.InvalidArgs'

class NotSupportedException(dbus.exceptions.DBusException):
    _dbus_error_name = 'org.bluez.Error.NotSupported'

class NotPermittedException(dbus.exceptions.DBusException):
    _dbus_error_name = 'org.bluez.Error.NotPermitted'

class InvalidValueLengthException(dbus.exceptions.DBusException):
    _dbus_error_name = 'org.bluez.Error.InvalidValueLength'

class FailedException(dbus.exceptions.DBusException):
    _dbus_error_name = 'org.bluez.Error.Failed'


class Application(dbus.service.Object):
    """
    org.bluez.GattApplication1 interface implementation
    """
    def __init__(self, bus):
        self.path = '/'
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(DBUS_OM_IFACE, out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        response = {}
        logger.info('GetManagedObjects')

        for service in self.services:
            response[service.get_path()] = service.get_properties()
            chrcs = service.get_characteristics()
            for chrc in chrcs:
                response[chrc.get_path()] = chrc.get_properties()
                descs = chrc.get_descriptors()
                for desc in descs:
                    response[desc.get_path()] = desc.get_properties()

        return response


class Service(dbus.service.Object):
    """
    org.bluez.GattService1 interface implementation
    """
    PATH_BASE = '/org/bluez/wpable/service'

    def __init__(self, bus, index, uuid, primary):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.uuid = uuid
        self.primary = primary
        self.characteristics = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
                GATT_SERVICE_IFACE: {
                        'UUID': self.uuid,
                        'Primary': self.primary,
                        'Characteristics': dbus.Array(
                                self.get_characteristic_paths(),
                                signature='o')
                }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_characteristic(self, characteristic):
        self.characteristics.append(characteristic)

    def get_characteristic_paths(self):
        result = []
        for chrc in self.characteristics:
            result.append(chrc.get_path())
        return result

    def get_characteristics(self):
        return self.characteristics

    @dbus.service.method(DBUS_PROP_IFACE,
                         in_signature='s',
                         out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != GATT_SERVICE_IFACE:
            raise InvalidArgsException()

        return self.get_properties()[GATT_SERVICE_IFACE]


class Characteristic(dbus.service.Object):
    """
    org.bluez.GattCharacteristic1 interface implementation
    """
    def __init__(self, bus, index, uuid, flags, service):
        self.path = service.path + '/char' + str(index)
        self.bus = bus
        self.uuid = uuid
        self.service = service
        self.flags = flags
        self.descriptors = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
                GATT_CHRC_IFACE: {
                        'Service': self.service.get_path(),
                        'UUID': self.uuid,
                        'Flags': self.flags,
                        'Descriptors': dbus.Array(
                                self.get_descriptor_paths(),
                                signature='o')
                }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_descriptor(self, descriptor):
        self.descriptors.append(descriptor)

    def get_descriptor_paths(self):
        result = []
        for desc in self.descriptors:
            result.append(desc.get_path())
        return result

    def get_descriptors(self):
        return self.descriptors

    @dbus.service.method(DBUS_PROP_IFACE,
                         in_signature='s',
                         out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != GATT_CHRC_IFACE:
            raise InvalidArgsException()

        return self.get_properties()[GATT_CHRC_IFACE]

    @dbus.service.method(GATT_CHRC_IFACE,
                        in_signature='a{sv}',
                        out_signature='ay')
    def ReadValue(self, options):
        logger.error('Default ReadValue called, returning error')
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE, in_signature='aya{sv}')
    def WriteValue(self, value, options):
        logger.error('Default WriteValue called, returning error')
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StartNotify(self):
        logger.error('Default StartNotify called, returning error')
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StopNotify(self):
        logger.error('Default StopNotify called, returning error')
        raise NotSupportedException()

    @dbus.service.signal(DBUS_PROP_IFACE,
                         signature='sa{sv}as')
    def PropertiesChanged(self, interface, changed, invalidated):
        pass


class Descriptor(dbus.service.Object):
    """
    org.bluez.GattDescriptor1 interface implementation
    """
    def __init__(self, bus, index, uuid, flags, characteristic):
        self.path = characteristic.path + '/desc' + str(index)
        self.bus = bus
        self.uuid = uuid
        self.flags = flags
        self.chrc = characteristic
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
                GATT_DESC_IFACE: {
                        'Characteristic': self.chrc.get_path(),
                        'UUID': self.uuid,
                        'Flags': self.flags,
                }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(DBUS_PROP_IFACE,
                         in_signature='s',
                         out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != GATT_DESC_IFACE:
            raise InvalidArgsException()

        return self.get_properties()[GATT_DESC_IFACE]

    @dbus.service.method(GATT_DESC_IFACE,
                        in_signature='a{sv}',
                        out_signature='ay')
    def ReadValue(self, options):
        logger.error('Default ReadValue called, returning error')
        raise NotSupportedException()

    @dbus.service.method(GATT_DESC_IFACE, in_signature='aya{sv}')
    def WriteValue(self, value, options):
        logger.error('Default WriteValue called, returning error')
        raise NotSupportedException()


class Advertisement(dbus.service.Object):
    PATH_BASE = '/org/bluez/wpable/advertisement'

    def __init__(self, bus, index, advertising_type):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.ad_type = advertising_type
        self.service_uuids = None
        self.manufacturer_data = None
        self.solicit_uuids = None
        self.service_data = None
        self.local_name = None
        self.include_tx_power = False
        self.data = None
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        properties = dict()
        properties['Type'] = self.ad_type
        if self.service_uuids is not None:
            properties['ServiceUUIDs'] = dbus.Array(self.service_uuids,
                                                    signature='s')
        if self.solicit_uuids is not None:
            properties['SolicitUUIDs'] = dbus.Array(self.solicit_uuids,
                                                    signature='s')
        if self.manufacturer_data is not None:
            properties['ManufacturerData'] = dbus.Dictionary(
                self.manufacturer_data, signature='qv')
        if self.service_data is not None:
            properties['ServiceData'] = dbus.Dictionary(self.service_data,
                                                        signature='sv')
        if self.local_name is not None:
            properties['LocalName'] = dbus.String(self.local_name)
        if self.include_tx_power:
            properties['Includes'] = dbus.Array(["tx-power"], signature='s')

        if self.data is not None:
            properties['Data'] = dbus.Dictionary(
                self.data, signature='yv')
        return {LE_ADVERTISEMENT_IFACE: properties}

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service_uuid(self, uuid):
        if not self.service_uuids:
            self.service_uuids = []
        self.service_uuids.append(uuid)

    def add_solicit_uuid(self, uuid):
        if not self.solicit_uuids:
            self.solicit_uuids = []
        self.solicit_uuids.append(uuid)

    def add_manufacturer_data(self, manuf_code, data):
        if not self.manufacturer_data:
            self.manufacturer_data = dbus.Dictionary({}, signature='qv')
        self.manufacturer_data[manuf_code] = dbus.Array(data, signature='y')

    def add_service_data(self, uuid, data):
        if not self.service_data:
            self.service_data = dbus.Dictionary({}, signature='sv')
        self.service_data[uuid] = dbus.Array(data, signature='y')

    def add_local_name(self, name):
        if not self.local_name:
            self.local_name = ""
        self.local_name = dbus.String(name)

    def add_data(self, ad_type, data):
        if not self.data:
            self.data = dbus.Dictionary({}, signature='yv')
        self.data[ad_type] = dbus.Array(data, signature='y')

    @dbus.service.method(DBUS_PROP_IFACE,
                         in_signature='s',
                         out_signature='a{sv}')
    def GetAll(self, interface):
        logger.info('GetAll')
        if interface != LE_ADVERTISEMENT_IFACE:
            raise InvalidArgsException()
        logger.info('Returning props')
        return self.get_properties()[LE_ADVERTISEMENT_IFACE]

    @dbus.service.method(LE_ADVERTISEMENT_IFACE,
                         in_signature='',
                         out_signature='')
    def Release(self):
        logger.info('%s: Released!' % self.path)


class Agent(dbus.service.Object):
    exit_on_release = True

    def set_exit_on_release(self, exit_on_release):
        self.exit_on_release = exit_on_release

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        logger.info("Release")
        if self.exit_on_release:
            mainloop.quit()

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        logger.info("AuthorizeService (%s, %s)" % (device, uuid))
        authorize = ask("Authorize connection (yes/no): ")
        if authorize == "yes":
            return
        raise Rejected("Connection rejected by user")

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        logger.info("RequestPinCode (%s)" % (device))
        set_trusted(device)
        return ask("Enter PIN Code: ")

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        logger.info("RequestPasskey (%s)" % (device))
        set_trusted(device)
        passkey = ask("Enter passkey: ")
        return dbus.UInt32(passkey)

    @dbus.service.method(AGENT_IFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        logger.info("DisplayPasskey (%s, %06u entered %u)" % (device, passkey, entered))

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        logger.info("DisplayPinCode (%s, %s)" % (device, pincode))

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        logger.info("RequestConfirmation (%s, %06d)" % (device, passkey))
        confirm = ask("Confirm passkey (yes/no): ")
        if confirm == "yes":
            set_trusted(device)
            return
        raise Rejected("Passkey doesn't match")

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        logger.info("RequestAuthorization (%s)" % (device))
        auth = ask("Authorize? (yes/no): ")
        if auth == "yes":
            return
        raise Rejected("Pairing rejected")

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Cancel(self):
        logger.info("Cancel")
        

class CharacteristicUserDescriptionDescriptor(Descriptor):
    """
    Writable CUD descriptor.
    """
    CUD_UUID = '2901'

    def __init__(self, bus, index, characteristic):
        self.writable = 'writable-auxiliaries' in characteristic.flags
        self.value = array.array('B', b'Registers characteristic user description (CUD) descriptors for the application')
        self.value = self.value.tolist()
        Descriptor.__init__(
                self, bus, index,
                self.CUD_UUID,
                ['read', 'write'],
                characteristic)

    def ReadValue(self, options):
        return self.value

    def WriteValue(self, value, options):
        if not self.writable:
            raise NotPermittedException()
        self.value = value


class Rejected(dbus.DBusException):
	_dbus_error_name = "org.bluez.Error.Rejected"


# https://wiki.archlinux.org/title/wpa_supplicant
WPA_SUPPLICANT_PATH = '/etc/wpa_supplicant/wpa_supplicant.conf'
WPA_COUNTRY_DEFAULT = 'US'
WPA_SSID_DEFAULT = ''
WPA_SCAN_SSID_DEFAULT = 1
WPA_PSK_DEFAULT = ''
WPA_KEY_MGMT_DEFAULT = 'WPA-PSK'

def parse(file_path):
    myvars = {}
    with open(file_path, 'r') as myfile:
        for line in myfile:
            name, var = line.partition("=")[::2]
            myvars[name.lower().strip()] = var.rstrip()
    return myvars

# Manages read/write from/to WPA_SUPPLICANT file
class WpaSupplicant():
    def __init__(self, file_path=WPA_SUPPLICANT_PATH):
        self.file_path = file_path
        self.params = self.defaults()

    def read(self):
        args = parse(self.file_path)
        for key, value in args.items():
            if key in self.params:
                self.params[key] = value
        return

    def write(self):
        with open(self.file_path, 'w') as myfile:
            myfile.write('ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n')
            myfile.write('update_config=1\n')
            myfile.write(f"country={self.params['country']}\n")
            myfile.write('network={\n')
            myfile.write(f"ssid=\"{self.params['ssid']}\"\n")
            myfile.write(f"scan_ssid={self.params['scan_ssid']}\n")
            myfile.write(f"psk=\"{self.params['psk']}\"\n")
            myfile.write(f"key_mgmt={self.params['key_mgmt']}\n")
            myfile.write('}')
        return

    def defaults(self):
        return {
            'country': WPA_COUNTRY_DEFAULT,
            'ssid': WPA_SSID_DEFAULT,
            'scan_ssid': WPA_SCAN_SSID_DEFAULT,
            'psk': WPA_PSK_DEFAULT,
            'key_mgmt': WPA_KEY_MGMT_DEFAULT
        }


# Moderates restarting the dhcpcd service
class DhcpMonitor():
    def __init__(self):
        self.__state = 'IDLE' # IDLE -> RESTART -> IDLE
        self.__process = None
        self.__start_time = None

    def state(self):
        try:
            if self.__state == 'RESTART':
                outs, errs = self.__process.communicate(timeout=1)
                self.__state = 'IDLE'
                self.__process = None
                stdouts = '<ok>' if not outs else outs.strip()
                stderrs = '<ok>' if not errs else errs.strip()
                logger.info("dhcpcd restarted: " + stdouts + " / " + stderrs)
        except subprocess.TimeoutExpired:
            if time.time() > self.__start_time + 15.0: # subprocess timed out
                self.__process.kill()
                self.__process = None
                self.__state = 'IDLE'
        return self.__state

    def restart(self):
        if self.__state == 'IDLE':
            self.__state = 'RESTART'
            self.__start_time = time.time()
            self.__process = subprocess.Popen(['systemctl', 'restart', 'dhcpcd'])


class WlanManageS1Service(Service):
    """
    Service to manage configuration of the local WLAN adapter.
    Allows a user to configure and restart the WLAN wpa_applicant service
    """

    WLANMANAGE_SVC_UUID = "12634d89-d598-4874-8e86-7d042ee07ba7"

    def __init__(self, bus, index):
        Service.__init__(self, bus, index, self.WLANMANAGE_SVC_UUID, True)
        self.add_characteristic(WlanConfigureCharacteristic(bus, 0, self))
        self.add_characteristic(WlanRestartCharacteristic(bus, 1, self))
        self.add_characteristic(WlanMacAddrCharacteristic(bus, 2, self))


class WlanConfigureCharacteristic(Characteristic):
    uuid = "4116f8d2-9f66-4f58-a53d-fc7440e7c14e"
    description = b"Configure WLAN interface {read:cur_config, write:new_config}"

    def __init__(self, bus, index, service):
        Characteristic.__init__(
            self, bus, index, self.uuid, ["read", "write"], service,
        )
        self.add_descriptor(CharacteristicUserDescriptionDescriptor(bus, 1, self))
        self.wpa = WpaSupplicant()

    def ReadValue(self, options):
        logger.info('Reading current WLAN configuration')
        # Load current wpa_supplicant values
        self.wpa.read()
        # Response is JSON-encoded dict as a string of bytes
        data = bytearray(json.dumps(self.wpa.params), 'utf-8')
        logger.info(data)
        return data

    def WriteValue(self, value, options):
        try:
            logger.info('Writing new WLAN configuration')
            # Load current wpa_supplicant values
            self.wpa.read()
            # Value is JSON-encoded dict as a string of bytes
            data = json.loads(bytearray(value).decode('utf-8')) # value is a dbus.Array
            logger.info(data)
            self.wpa.params = data
            self.wpa.write()
        except Exception as e:
            logger.error(f"EXCEPTION: {e}")
            raise


class WlanRestartCharacteristic(Characteristic):
    uuid = "9c7dbce8-de5f-4168-89dd-74f04f4e5842"
    description = b"Restart the WLAN interface {read:state, write:state}"

    def __init__(self, bus, index, service):
        Characteristic.__init__(
            self, bus, index, self.uuid, ["read", "write"], service,
        )
        self.add_descriptor(CharacteristicUserDescriptionDescriptor(bus, 1, self))
        self.dhcpcd_monitor = DhcpMonitor()

    def ReadValue(self, options):
        logger.info('Reading restart state')
        data = bytearray(self.dhcpcd_monitor.state(), 'utf-8')
        logger.info(data)
        return data

    def WriteValue(self, value, options):
        try:
            logger.info("Writing restart state")
            data = bytearray(value).decode('utf-8') # value is a dbus.Array
            logger.info(data)
            # Have to be idle to do anything else
            if self.dhcpcd_monitor.state() == 'IDLE':
                # Now check to see if command is restart
                if data == 'RESTART':
                    # Restart the wpa_supplicant service
                    self.dhcpcd_monitor.restart()
                else:
                    # Don't know this command, ignore
                    logger.info("Unknown restart state")
            else:
                # Not idle, do nothing...
                pass
        except Exception as e:
            logger.error(f"EXCEPTION: {e}")
            raise


class WlanMacAddrCharacteristic(Characteristic):
    uuid = "16637984-be04-49b8-be43-86cf4efda929"
    description = b"Retrieve the wireless interface MAC address {read:addr}"

    def __init__(self, bus, index, service):
        Characteristic.__init__(
            self, bus, index, self.uuid, ["read"], service,
        )
        self.value = get_if_hwaddr(DEFAULT_WLAN_IFACE)
        self.add_descriptor(CharacteristicUserDescriptionDescriptor(bus, 1, self))

    def ReadValue(self, options):
        logger.info('Reading WLAN interface MAC address')
        data = bytearray(self.value, 'utf-8')
        logger.info(data)
        return data


class WlanSetupAdvertisement(Advertisement):
    def __init__(self, bus, index):
        Advertisement.__init__(self, bus, index, "peripheral")
        self.add_manufacturer_data(
            0xFFFF, [0x70, 0x74],
        )
        self.add_service_uuid(WlanManageS1Service.WLANMANAGE_SVC_UUID)
        self.add_local_name(WLAN_IFACE_BT_NAME)
        self.include_tx_power = True


def register_app_cb():
    logger.info('GATT application registered')


def register_app_error_cb(error):
    logger.critical('Failed to register application: ' + str(error))
    mainloop.quit()


def register_ad_cb():
    logger.info('Advertisement registered')


def register_ad_error_cb(error):
    logger.critical('Failed to register advertisement: ' + str(error))
    mainloop.quit()


def ask(prompt):
	try:
		return raw_input(prompt)
	except:
		return input(prompt)


def dev_connect(path):
	dev = dbus.Interface(bus.get_object("org.bluez", path),	"org.bluez.Device1")
	dev.Connect()


def find_adapter(bus):
    remote_om = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, '/'),
                               DBUS_OM_IFACE)
    objects = remote_om.GetManagedObjects()

    for o, props in objects.items():
        if GATT_MANAGER_IFACE in props.keys():
            return o

    return None


def set_trusted(path):
	props = dbus.Interface(bus.get_object("org.bluez", path),
					"org.freedesktop.DBus.Properties")
	props.Set("org.bluez.Device1", "Trusted", True)


def main():
    global mainloop

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    bus = dbus.SystemBus()

    adapter = find_adapter(bus)
    if not adapter:
        logger.critical("GattManager1 interface not found")
        return

    adapter_obj = bus.get_object(BLUEZ_SERVICE_NAME, adapter)

    adapter_props = dbus.Interface(adapter_obj, "org.freedesktop.DBus.Properties")

    # powered property on the controller to on
    adapter_props.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(1))

    # Get manager objs
    service_manager = dbus.Interface(adapter_obj, GATT_MANAGER_IFACE)
    ad_manager = dbus.Interface(adapter_obj, LE_ADVERTISING_MANAGER_IFACE)

    advertisement = WlanSetupAdvertisement(bus, 0)
    bluez_obj = bus.get_object(BLUEZ_SERVICE_NAME, "/org/bluez")

    agent = Agent(bus, AGENT_PATH)

    app = Application(bus)
    app.add_service(WlanManageS1Service(bus, 0))

    agent_manager = dbus.Interface(bluez_obj, "org.bluez.AgentManager1")
    agent_manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")

    ad_manager.RegisterAdvertisement(
        advertisement.get_path(),
        {},
        reply_handler=register_ad_cb,
        error_handler=register_ad_error_cb,
    )

    logger.info("Registering GATT application")

    service_manager.RegisterApplication(
        app.get_path(),
        {},
        reply_handler=register_app_cb,
        error_handler=[register_app_error_cb],
    )

    agent_manager.RequestDefaultAgent(AGENT_PATH)

    mainloop.run()

if __name__ == '__main__':
    main()
