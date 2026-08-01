"""
ctypes layout for rFactorSharedMemoryMap.dll (v2.0.0.0).
Shared memory name: $rFactorShared$
"""

from ctypes import (
    Structure,
    c_bool,
    c_char,
    c_float,
    c_int8,
    c_long,
    c_short,
    c_ubyte,
)


class rfStruct(Structure):
    _pack_ = 1


class rfVec3(rfStruct):
    _fields_ = [
        ("x", c_float),
        ("y", c_float),
        ("z", c_float),
    ]


class rfWheel(rfStruct):
    _fields_ = [
        ("rotation", c_float),  # rad/s
        ("suspensionDeflection", c_float),  # m
        ("rideHeight", c_float),  # m
        ("tireLoad", c_float),  # N
        ("lateralForce", c_float),  # N
        ("gripFract", c_float),
        ("brakeTemp", c_float),  # C
        ("pressure", c_float),  # kPa
        ("temperature", c_float * 3),  # C left/center/right
        ("wear", c_float),  # 0..1
        ("terrainName", c_char * 16),
        ("surfaceType", c_ubyte),
        ("flat", c_bool),
        ("detached", c_bool),
    ]


class rfVehicleInfo(rfStruct):
    _fields_ = [
        ("driverName", c_char * 32),
        ("vehicleName", c_char * 64),
        ("totalLaps", c_short),
        ("sector", c_int8),
        ("finishStatus", c_int8),
        ("lapDist", c_float),
        ("pathLateral", c_float),
        ("trackEdge", c_float),
        ("bestSector1", c_float),
        ("bestSector2", c_float),
        ("bestLapTime", c_float),
        ("lastSector1", c_float),
        ("lastSector2", c_float),
        ("lastLapTime", c_float),
        ("curSector1", c_float),
        ("curSector2", c_float),
        ("numPitstops", c_short),
        ("numPenalties", c_short),
        ("isPlayer", c_bool),
        ("control", c_int8),
        ("inPits", c_bool),
        ("place", c_ubyte),
        ("vehicleClass", c_char * 32),
        ("timeBehindNext", c_float),
        ("lapsBehindNext", c_long),
        ("timeBehindLeader", c_float),
        ("lapsBehindLeader", c_long),
        ("lapStartET", c_float),
        ("pos", rfVec3),
        ("localVel", rfVec3),
        ("localAccel", rfVec3),
        ("oriX", rfVec3),
        ("oriY", rfVec3),
        ("oriZ", rfVec3),
        ("localRot", rfVec3),
        ("localRotAccel", rfVec3),
        ("speed", c_float),
    ]


class rfShared(rfStruct):
    _fields_ = [
        ("deltaTime", c_float),
        ("lapNumber", c_long),
        ("lapStartET", c_float),
        ("vehicleName", c_char * 64),
        ("trackName", c_char * 64),
        ("pos", rfVec3),
        ("localVel", rfVec3),
        ("localAccel", rfVec3),
        ("oriX", rfVec3),
        ("oriY", rfVec3),
        ("oriZ", rfVec3),
        ("localRot", rfVec3),
        ("localRotAccel", rfVec3),
        ("speed", c_float),
        ("gear", c_long),
        ("engineRPM", c_float),
        ("engineWaterTemp", c_float),
        ("engineOilTemp", c_float),
        ("clutchRPM", c_float),
        ("unfilteredThrottle", c_float),
        ("unfilteredBrake", c_float),
        ("unfilteredSteering", c_float),
        ("unfilteredClutch", c_float),
        ("steeringArmForce", c_float),
        ("fuel", c_float),
        ("engineMaxRPM", c_float),
        ("scheduledStops", c_ubyte),
        ("overheating", c_bool),
        ("detached", c_bool),
        ("dentSeverity", c_ubyte * 8),
        ("lastImpactET", c_float),
        ("lastImpactMagnitude", c_float),
        ("lastImpactPos", rfVec3),
        ("wheel", rfWheel * 4),
        ("session", c_long),
        ("currentET", c_float),
        ("endET", c_float),
        ("maxLaps", c_long),
        ("lapDist", c_float),
        ("numVehicles", c_long),
        ("gamePhase", c_ubyte),
        ("yellowFlagState", c_int8),
        ("sectorFlag", c_int8 * 3),
        ("startLight", c_ubyte),
        ("numRedLights", c_ubyte),
        ("inRealtime", c_bool),
        ("playerName", c_char * 32),
        ("plrFileName", c_char * 64),
        ("ambientTemp", c_float),
        ("trackTemp", c_float),
        ("wind", rfVec3),
        ("vehicle", rfVehicleInfo * 128),
    ]


RF_MAP_TAG = "$rFactorShared$"

GAME_PHASE = {
    0: "garage",
    1: "warmUp",
    2: "gridWalk",
    3: "formation",
    4: "countdown",
    5: "greenFlag",
    6: "fullCourseYellow",
    7: "sessionStopped",
    8: "sessionOver",
}


def decode_c_str(value: bytes) -> str:
    return value.split(b"\x00", 1)[0].decode("latin-1", errors="replace")


def mps_to_kph(mps: float) -> float:
    return mps * 3.6
