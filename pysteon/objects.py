"""
Objects.
"""

from enum import IntEnum


class Identity(object):
    """
    Represents an identity.
    """

    def __init__(self, id_):
        assert len(id_) == 3
        self.id_ = bytes(id_)

    def __eq__(self, value):
        if not isinstance(value, Identity):
            return NotImplemented

        return self.id_ == value.id_

    def __bytes__(self):
        return self.id_

    def __repr__(self):
        return repr(bytes(self))

    def __str__(self):
        return '%02x.%02x.%02x' % tuple(self.id_)


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


class DeviceCategory(IntEnum):
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
        self.title = "Unknown device category (%02x)" % self.value
        self.examples = ""
        self.subcategory_class = GenericSubcategory

    def __eq__(self, value):
        if not isinstance(value, GenericDeviceCategory):
            return NotImplemented

        return value.value == self.value


class GeneralizedControllersSubcategory(IntEnum):
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


class DimmableLightingControlSubcategory(IntEnum):
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


class SwitchedLightingControlSubcategory(IntEnum):
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


class NetworkBridgesSubcategory(IntEnum):
    powerlinc_serial = 0x01
    powerlinc_usb = 0x02
    icon_powerlinc_serial = 0x03
    icon_powerlinc_usb = 0x04
    smartlabs_power_line_modem_serial = 0x05

    @property
    def title(self):
        return {
            self.powerlinc_serial: "PowerLinc Serial [2414S]",
            self.powerlinc_usb: "PowerLinc USB [2414U]",
            self.icon_powerlinc_serial: "Icon PowerLinc Serial [2814 S]",
            self.icon_powerlinc_usb: "Icon PowerLinc USB [2814U] ",
            self.smartlabs_power_line_modem_serial:
            "Smartlabs Power Line Modem Serial [2412S]",
        }[self]


class IrrigationControlSubcategory(IntEnum):
    compacta_ezrain_sprinkler_controller = 0x00

    @property
    def title(self):
        return {
            self.compacta_ezrain_sprinkler_controller:
            "Compacta EZRain Sprinkler Controller",
        }[self]



class ClimateControlSubcategory(IntEnum):
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


class PoolAndSpaControlSubcategory(IntEnum):
    compacta_ezpool = 0x00

    @property
    def title(self):
        return {
            self.compacta_ezpool: "Compacta EZPool",
        }[self]


class SensorsAndActuatorsSubcategory(IntEnum):
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

    def __eq__(self, value):
        if not isinstance(value, GenericSubcategory):
            return NotImplemented

        return value.value == self.value
