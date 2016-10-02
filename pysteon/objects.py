"""
Objects.
"""

from collections import namedtuple
from enum import (
    Enum,
    IntEnum,
)


class Identity(bytes):
    """
    Represents an identity.
    """

    def __new__(cls, id_):
        assert len(id_) == 3
        return super().__new__(cls, id_)

    def __str__(self):
        return '%02x.%02x.%02x' % tuple(self)


def parse_device_categories(value):
    """
    Parse a device categories buffer of 2 bytes.

    :param value: A 2-bytes long array.
    :returns: A tuple of (devcat, subcat).
    """
    assert len(value) == 2

    try:
        devcat = DeviceCategory(value[0])
    except ValueError:
        devcat = GenericDeviceCategory(value[0])

    try:
        subcat = devcat.subcategory_class(value[1])
    except ValueError:
        subcat = GenericSubcategory(value[1])

    return devcat, subcat


class TitleIntEnum(IntEnum):
    """
    A base class for IntEnum with titles.
    """

    def __repr__(self):
        return '%s(0x%02x)' % (self.__class__.__name__, self.value)

    def __str__(self):
        return self.title


class DeviceCategory(TitleIntEnum):
    """
    All the device categories, as defined at:
    http://cache.insteon.com/pdf/INSTEON_Developers_Guide_20070816a.pdf, page
    83.
    """
    generalized_controllers = 0x00
    dimmable_lighting_control = 0x01
    switched_lighting_control = 0x02
    network_bridges = 0x03
    irrigation_control = 0x04
    climate_control_heating = 0x05
    pool_and_spa_control = 0x06
    sensors_and_actuators = 0x07
    home_entertainement = 0x08
    energy_management = 0x09
    built_in_appliance_control = 0x0A
    plumbing = 0x0B
    communication = 0x0C
    computer_control = 0x0D
    window_coverings = 0x0E
    access_control = 0x0F
    security_health_safety = 0x10
    surveillance = 0x11
    automotive = 0x12
    pet_care = 0x13
    toys = 0x14
    timekeeping = 0x15
    holiday = 0x16
    unassigned = 0xFF

    @property
    def title(self):
        return {
            self.generalized_controllers: "Generalized Controllers",
            self.dimmable_lighting_control: "Dimmable Lighting Control",
            self.switched_lighting_control: "Switched Lighting Control",
            self.network_bridges: "Network Bridges",
            self.irrigation_control: "Irrigation Control",
            self.climate_control_heating: "Climate Control",
            self.pool_and_spa_control: "Pool and Spa Control",
            self.sensors_and_actuators: "Sensors and Actuators",
            self.home_entertainement: "Home Entertainment",
            self.energy_management: "Energy Management",
            self.built_in_appliance_control: "Built-In Appliance Control",
            self.plumbing: "Plumbing",
            self.communication: "Communication",
            self.computer_control: "Computer Control",
            self.window_coverings: "Window Coverings",
            self.access_control: "Access Control",
            self.security_health_safety: "Security, Health, Safety",
            self.surveillance: "Surveillance",
            self.automotive: "Automotive",
            self.pet_care: "Pet Care",
            self.toys: "Toys",
            self.timekeeping: "Timekeeping",
            self.holiday: "Holiday",
            self.unassigned: "Unassigned",
        }[self]

    @property
    def examples(self):
        return {
            self.generalized_controllers:
            "ControLinc, RemoteLinc, SignaLinc, etc",
            self.dimmable_lighting_control:
            "Dimmable Light Switches, Dimmable Plug-In Module",
            self.switched_lighting_control:
            "Relay Switches, Relay Plug-In Module",
            self.network_bridges:
            "PowerLinc Controllers, TRex, Lonworks, ZigBee, etc",
            self.irrigation_control:
            "Irrigation Management, Sprinkler Controller",
            self.climate_control_heating:
            "Heating, Air conditioning, Exhausts Fans, Ceiling Fans, Indoor "
            "Air Quality",
            self.pool_and_spa_control:
            "Pumps, Heaters, Chemical",
            self.sensors_and_actuators:
            "Sensors, Contact Closure",
            self.home_entertainement:
            "Audio/Video Equipmen",
            self.energy_management:
            "Electricity, Water, Gas Consumption, Leak Monitor",
            self.built_in_appliance_control:
            "White Goods, Brown Good",
            self.plumbing:
            "Faucets, Showers, Toilet",
            self.communication:
            "Telephone System Controls, Intercom",
            self.computer_control:
            "PC On/Off, UPS Control, App Activation, Remote Mouse, Keyboard",
            self.window_coverings:
            "Drapes, Blinds, Awning",
            self.access_control:
            "Automatic Doors, Gates, Windows, Lock",
            self.security_health_safety:
            "Door and Window Sensors, Motion Sensors, Scale",
            self.surveillance:
            "Video Camera Control, Time-lapse Recorders, Security System Link",
            self.automotive:
            "Remote Starters, Car Alarms, Car Door Lock",
            self.pet_care:
            "Pet Feeders, Tracker",
            self.toys:
            "Model Trains, Robot",
            self.timekeeping:
            "Clocks, Alarms, Timer",
            self.holiday:
            "Christmas Lights, Display",
            self.unassigned:
            "For devices that will be assigned a DevCat and SubCat by "
            "software",
        }[self]

    @property
    def subcategory_class(self):
        return {
            self.generalized_controllers: GeneralizedControllersSubcategory,
            self.dimmable_lighting_control: DimmableLightingControlSubcategory,
            self.switched_lighting_control: SwitchedLightingControlSubcategory,
            self.network_bridges: NetworkBridgesSubcategory,
            self.irrigation_control: IrrigationControlSubcategory,
            self.climate_control_heating: ClimateControlSubcategory,
            self.pool_and_spa_control: PoolAndSpaControlSubcategory,
            self.sensors_and_actuators: SensorsAndActuatorsSubcategory,
        }.get(self, GenericSubcategory)


class GenericDeviceCategory(object):
    def __init__(self, value):
        self.value = value
        self.title = "Unknown device category (0x%02x)" % self.value
        self.examples = ""
        self.subcategory_class = GenericSubcategory

    def __repr__(self):
        return 'GenericDeviceCategory(0x%02x)' % self.value

    def __str__(self):
        return self.title

    def __eq__(self, value):
        if not isinstance(value, GenericDeviceCategory):
            return NotImplemented

        return value.value == self.value


class GeneralizedControllersSubcategory(TitleIntEnum):
    controlink = 0x04
    remotelinc = 0x05
    icon_tabletop_controller = 0x06
    signalinc_rf_signal_enhancer = 0x09
    balboa_instruments_poolux_lcd_controller = 0x0a
    access_point = 0x0b
    ies_color_touchscreen = 0x0c

    @property
    def title(self):
        return {
            self.controlink: "ControLinc [2430]",
            self.remotelinc: "RemoteLinc [2440]",
            self.icon_tabletop_controller: "Icon Tabletop Controller [2830]",
            self.balboa_instruments_poolux_lcd_controller:
            "Balboa Instruments Poolux LCD Controller",
            self.access_point: "Access Point",
            self.ies_color_touchscreen: "IES Color Touchscreen",
        }[self]


class DimmableLightingControlSubcategory(TitleIntEnum):
    lamplinc_v2 = 0x00
    switchlinc_v2_dimmer_600w = 0x01
    in_linelinc_dimmer = 0x02
    icon_switch_dimmer = 0x03
    switchlinc_v2_dimmer_1000w = 0x04
    lamplinc_2pin = 0x06
    icon_lamplinc_v2_2pin = 0x07
    keypadlinc_dimmer = 0x09
    icon_in_wall_controller = 0x0a
    socketlinc = 0x0d
    icon_switchlinc_dimmer_for_lixer_bell_canada = 0x13
    togglelinc_dimmer = 0x17

    @property
    def title(self):
        return {
            self.lamplinc_v2: "LampLinc V2 [2456D3]",
            self.switchlinc_v2_dimmer_600w:
            "SwitchLinc V2 Dimmer 600W [2476D]",
            self.in_linelinc_dimmer: "In-LineLinc Dimmer [2475D]",
            self.icon_switch_dimmer: "Icon Switch Dimmer [2876D]",
            self.switchlinc_v2_dimmer_1000w:
            "SwitchLinc V2 Dimmer 1000W [2476DH]",
            self.lamplinc_2pin: "LampLinc 2-Pin [2456D2]",
            self.icon_lamplinc_v2_2pin: "Icon LampLinc V2 2-Pin [2456D2]",
            self.keypadlinc_dimmer: "KeypadLinc Dimmer [2486D]",
            self.icon_in_wall_controller: "Icon In-Wall Controller [2886D]",
            self.socketlinc: "SocketLinc [2454D]",
            self.icon_switchlinc_dimmer_for_lixer_bell_canada:
            "Icon SwitchLinc Dimmer for Lixar/Bell Canada [2676D-B]",
            self.togglelinc_dimmer: "ToggleLinc Dimmer [2466D]",
        }[self]


class SwitchedLightingControlSubcategory(TitleIntEnum):
    appliancelinc = 0x09
    switchlinc_relay = 0x0a
    icon_on_off_switch = 0x0b
    icon_appliance_adapter = 0x0c
    togglelinc_relay = 0x0d
    switchlinc_relay_countdown_timer = 0x0e
    in_linelinc_relay = 0x10
    icon_switchlinc_relay_for_lixar_bell_canada = 0x013

    @property
    def title(self):
        return {
            self.appliancelinc: "ApplianceLinc [2456S3]",
            self.switchlinc_relay: "SwitchLinc Relay [2476S]",
            self.icon_on_off_switch: "Icon On Off Switch [2876S]",
            self.icon_appliance_adapter: "Icon Appliance Adapter [2856S3]",
            self.togglelinc_relay: "ToggleLinc Relay [2466S]",
            self.switchlinc_relay_countdown_timer:
            "SwitchLinc Relay Countdown Timer [2476ST]",
            self.in_linelinc_relay: "In-LineLinc Relay [2475D]",
            self.icon_switchlinc_relay_for_lixar_bell_canada:
            "Icon SwitchLinc Relay for Lixar/Bell Canada [2676R-B]",
        }[self]


class NetworkBridgesSubcategory(TitleIntEnum):
    powerlinc_serial = 0x01
    powerlinc_usb = 0x02
    icon_powerlinc_serial = 0x03
    icon_powerlinc_usb = 0x04
    smartlabs_power_line_modem_serial = 0x05
    powerlinc_dual_band_serial = 0x11
    powerlinc_dual_band_usb = 0x15

    @property
    def title(self):
        return {
            self.powerlinc_serial: "PowerLinc Serial [2414S]",
            self.powerlinc_usb: "PowerLinc USB [2414U]",
            self.icon_powerlinc_serial: "Icon PowerLinc Serial [2814 S]",
            self.icon_powerlinc_usb: "Icon PowerLinc USB [2814U] ",
            self.smartlabs_power_line_modem_serial:
            "Smartlabs Power Line Modem Serial [2412S]",
            self.powerlinc_dual_band_serial:
            "PowerLinc Dual Band Serial [2413S]",
            self.powerlinc_dual_band_usb: "PowerLinc Dual Band USB [2413U]",
        }[self]


class IrrigationControlSubcategory(TitleIntEnum):
    compacta_ezrain_sprinkler_controller = 0x00

    @property
    def title(self):
        return {
            self.compacta_ezrain_sprinkler_controller:
            "Compacta EZRain Sprinkler Controller",
        }[self]


class ClimateControlSubcategory(TitleIntEnum):
    broan_smsc080_exhaust_fan = 0x00
    compacta_eztherm = 0x01
    broan_smsc110_exhaust_fan = 0x02
    venstar_rf_thermostat_module = 0x03
    compacta_ezthermx_thermostat = 0x04

    @property
    def title(self):
        return {
            self.broan_smsc080_exhaust_fan: "Broan SMSC080 Exhaust Fan",
            self.compacta_eztherm: "Compacta EZTherm",
            self.broan_smsc110_exhaust_fan: "Broan SMSC110 Exhaust Fan",
            self.venstar_rf_thermostat_module: "Venstar RF Thermostat Module",
            self.compacta_ezthermx_thermostat: "Compacta EZThermx Thermostat",
        }[self]


class PoolAndSpaControlSubcategory(TitleIntEnum):
    compacta_ezpool = 0x00

    @property
    def title(self):
        return {
            self.compacta_ezpool: "Compacta EZPool",
        }[self]


class SensorsAndActuatorsSubcategory(TitleIntEnum):
    iolinc = 0x00

    @property
    def title(self):
        return {
            self.iolinc: "IOLinc",
        }[self]


class GenericSubcategory(object):
    def __init__(self, value):
        self.value = value
        self.title = "Unknown subcategory (%02x)" % self.value

    def __repr__(self):
        return 'GenericSubcategory(0x%02x)' % self.value

    def __str__(self):
        return self.title

    def __eq__(self, value):
        if not isinstance(value, GenericSubcategory):
            return NotImplemented

        return value.value == self.value


def parse_all_link_record_response(value):
    """
    Parse an All-Link record response.

    :param value: The buffer to parse.
    :returns: An `AllLinkRecordResponse` instance.
    """
    assert len(value) == 8

    return AllLinkRecord(
        identity=Identity(value[2:5]),
        group=value[1],
        role=AllLinkRole(bool(value[0] & 0x40)),
        data=value[5:8],
    )



class AllLinkRole(Enum):
    responder = True
    controller = False

    def __str__(self):
        if self is AllLinkRole.controller:
            return 'controller'
        else:
            return 'responder'


class AllLinkMode(IntEnum):
    responder = 0x00
    controller = 0x01
    auto = 0x03
    unknown = 0xfe
    delete = 0xff

    @classmethod
    def from_string(cls, value):
        try:
            return getattr(cls, value)
        except AttributeError:
            raise ValueError(value)

    def __str__(self):
        return self.name


class AllLinkRecord(
    namedtuple(
        '_AllLinkRecord',
        [
            'role',
            'identity',
            'group',
            'data',
        ],
    ),
):
    def __str__(self):
        return "%s-%02x (%s, %s)" % (
            self.identity,
            self.group,
            self.role,
            self.data.hex(),
        )


class InsteonMessageFlag(IntEnum):
    extended = 4
    ack = 5
    all_link = 6
    broadcast = 7


class InsteonMessage(
    namedtuple(
        '_InsteonMessage',
        [
            'sender',
            'target',
            'hops_left',
            'max_hops',
            'flags',
            'command_bytes',
            'user_data',
        ],
    ),
):
    @classmethod
    def from_message(cls, message):
        flags_byte = message.body[6]
        max_hops = flags_byte & 0x03
        hops_left = (flags_byte & 0x0c) >> 2
        flags = {
            flag for flag in InsteonMessageFlag
            if (flags_byte & (1 << flag.value)) != 0
        }

        return cls(
            sender=Identity(message.body[0:3]),
            target=Identity(message.body[3:6]),
            hops_left=hops_left,
            max_hops=max_hops,
            flags=flags,
            command_bytes=message.body[7:9],
            user_data=message.body[9:],
        )

    def __str__(self):
        return (
            "{self.sender} -> {self.target} "
            "[{self.hops_left}/{self.max_hops}]: {command_bytes} ({flags}) "
            "({user_data})"
        ).format(
            self=self,
            command_bytes=self.command_bytes.hex(),
            flags=', '.join(flag.name for flag in self.flags),
            user_data=self.user_data.hex(),
        )
