#!/root/.pyenv/shims/python

"""
Piglow vanity job that pings home router, if success, iterate
along a leg (0). animation for ping (leg 1), and perhaps 
animation for response (2).

To start, run as a python script only. Later, call in cron,
and don't clear iteration leg(0) for long term viz. 6 LEDs
on a leg imply 10 minute checks can cover each hour. 

Intended to be called via cron

note: must call pyenv python.
TODO: figure out how to call pyenv python from cron
TODO: while ping can accept -c, and it would be nice to light at each
    call, I can't think of any way to interupt/catch each response... 
TODO: swap animate_ping to threaded - blinking and turning off independently
"""

from typing import Any, List

from datetime import datetime
from enum import IntEnum
import logging
from pathlib import Path
import platform
import subprocess
import time

import piglow

piglow.clear_on_exit = False
piglow.auto_update = True

# ROUTER AND LOG VARS
IP = "192.168.1.1"
LOG = Path("/root/wifi_debug/ping_router_piglow.log")
TEST_LOG = Path("/root/wifi_debug/ping_router_dev.log")
LEVEL = logging.DEBUG

logging.basicConfig(
        format="%(asctime)s %(message)s",
        filename=TEST_LOG, 
        encoding='utf-8', 
        level=LEVEL)

# LEGS (make ENUMS?!)
# from outside to inside 
Ping = IntEnum("Ping", ["ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE"], start=0)
Resp = IntEnum("Resp", ["SIX", "SEVEN", "EIGHT", "NINE", "TEN", "ELEVEN"], start=6)
Cron = IntEnum("Cron", ["TWELVE","THIRTEEN", "FOURTEEN", "FIFTEEN",
                        "SIXTEEN", "SEVENTEEN"], start=12)
Legs = IntEnum("Legs", ["ZERO", "ONE", "TWO", ], start=0)

def ping_router(ip="192.168.1.1", c: int = 1) -> Any:
    """ Subprocess call to router via ping. 

    Captured response is sent to leg animations.
    Args:
        -c: count, 6, ping 6 times, once for each leg LED
        ip: IPV6 address (default home router)
    returns: 
        response from system ping, string
    """ 
    command = ["ping", "-c", str(c), ip] 
    logging.debug(f"Pinging home router {ip = }, {c} times") 
    responses = []
    for led in reversed(Ping):
        try:
            #print(f"pinging with {led = }")
            animate_ping(led=led)
            resp = subprocess.check_output(command).decode()
            #print(resp)
            responses.append(resp)
        except Exception as e:
            logging.error(f"Ping failed: {e = }")
            responses.append(e)
        time.sleep(1)
    return responses

def animate_ping(led: Ping, err_blink=False):
    piglow.set(led, 64)

def animate_responses(responses: str, leg = Resp):
    """Animate leg=1 for ping responses. blink if errored, solid of success
    
    For now, assume 6 pings. later can modulo maybe"""

    for led, response in zip(reversed(leg), responses):
        #print(f"{response= }")
        if "0% packet loss".lower() in response:
            piglow.set(led, 32)
        else:
            blink(led, 64)

    if all(["0% packet loss" in c for c in responses]):
        blink_leg(Legs.ONE)
        piglow.arm(Legs.ONE, 32) 

    time.sleep(2.5)
    leg_off(Legs.ONE)

def animate_cron(responses: List[str], trial: int, leg: IntEnum = Cron):
    """Animate leg 2, showing successful full ping checks. 

    When a check as >80% packet transmission, consider it a successful
    ping check; light up an LED. Else consider it a failed ping check, 
    and that LED is off. Base case is 10 checks per hour (6 LEDS), but 
    can refactor for a modulo, s.t. any time interval loops through 
    the leg enum. 
    """
    threshold = 0.8

    hit_rate = sum(["0% packet loss" in c for c in responses]) \
                     / len(responses)
    #print(f"reached {hit_rate = }")
    trial_success = hit_rate >= threshold 
    #print(f"lighting led: {leg(trial) = }")
    blink(leg(trial))
    piglow.set(leg(trial), 64)

    # turn off two-past led on Cron leg
    # trial-2 will be in: [12,17]
    #back_two = [16, 17, 12, 13, 14, 15]
    back_two = {12:16, 13:17, 14:12, 15:13, 16:14, 17:15}
    piglow.set(leg(back_two[trial]), 0)


def blink(led: IntEnum, blinks=6):
    for i in range(blinks):
        piglow.set(led, 64)
        time.sleep(0.25)
        piglow.set(led, 0)
        time.sleep(0.25)

def blink_leg(leg: IntEnum, blinks= 6):
    for i in range(blinks):
        piglow.leg(leg, 64)
        time.sleep(0.25)
        piglow.leg(leg, 0)
        time.sleep(0.25)
    

def leg_off(leg: IntEnum):
    piglow.arm(leg, 0)

if __name__ == "__main__":
    # add 12 to reach Cron value
    trial = (datetime.now().minute % 6) + 12
    res = ping_router(ip=IP)
    animate_responses(res)
    animate_cron(res, trial)
