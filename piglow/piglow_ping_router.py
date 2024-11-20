#!/root/.pyenv/versions/3.11.2/envs/gpio-3.11/bin/python3.11

"""
Piglow vanity job that pings home router, if success, iterate
along a leg (0). animation for ping (leg 1), and perhaps 
animation for response (2).

To start, run as a python script only. Later, call in cron,
and don't clear iteration leg(0) for long term viz. 6 LEDs
on a leg imply 10 minute checks can cover each hour. 

Intended to be called via cron

TODO: while ping can accept -c, and it would be nice to light at each
    call, I can't think of any way to interupt/catch each response... 
TODO: swap animate_ping to threaded - blinking and turning off independently
"""

from typing import Any, Dict, List, Set, Tuple

from datetime import datetime
from enum import IntEnum
import logging
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

import piglow

piglow.clear_on_exit = False
piglow.auto_update = True

# ROUTER AND LOG VARS
IP = "192.168.1.1"
LOG = Path("/root/wifi_debug/ping_router_cron.log")
TEST_LOG = Path("/root/wifi_debug/ping_router_dev.log")
LEVEL = logging.DEBUG

logging.basicConfig(
        format="%(asctime)s %(message)s",
        filename=TEST_LOG, 
        encoding='utf-8', 
        level=LEVEL)

# LEGS
# from outside to inside 
Ping = IntEnum("Ping", ["ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE"], start=0)
Resp = IntEnum("Resp", ["SIX", "SEVEN", "EIGHT", "NINE", "TEN", "ELEVEN"], start=6)
Cron = IntEnum("Cron", ["TWELVE","THIRTEEN", "FOURTEEN", "FIFTEEN",
                        "SIXTEEN", "SEVENTEEN"], start=12)
Legs = IntEnum("Legs", ["ZERO", "ONE", "TWO", ], start=0)
# OTHER CONSTANTS
POWER = 32    # led brightness - won't be same lumin for all colours. meh

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
    logging.debug(f"Pinging home router {ip = }, {c*len(Ping)} times") 
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
            piglow.off()
            sys.exit(1)
        time.sleep(1)
    return responses

def animate_ping(led: Ping, err_blink=False):
    piglow.set(led, POWER)

def animate_responses(responses: str, leg = Resp):
    """Animate leg=1 for ping responses. blink if errored, solid of success
    
    For now, assume 6 pings. later can modulo maybe"""

    for led, response in zip(reversed(leg), responses):
        if "0% packet loss".lower() in response:
            piglow.set(led, POWER)
        else:
            blink(led, POWER)

    if all(["0% packet loss" in c for c in responses]):
        blink_leg(Legs.ONE)
        piglow.arm(Legs.ONE, POWER) 

    time.sleep(2.5)
    leg_off(Legs.ONE)

def animate_cron(responses: List[str], trial: int, leg: IntEnum = Cron) -> Tuple[Set, Set]:
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
    # blink and hold on success
    trial_success = hit_rate >= threshold 
    if trial_success: 
        blink(leg(trial), blinks=2)
        piglow.set(leg(trial), POWER)
    # keep blinking on failure
    else:
        blink(leg(trial), blinks=15) 

    # turn off two-past led on Cron leg
    back_two = {12:16, 13:17, 14:12, 15:13, 16:14, 17:15}
    piglow.set(leg(back_two[trial]), 0)
    
    # track state
    on = {leg(trial).value} if trial_success else set()
    off = {back_two[trial]}
    state = {"on": on, "off": off}
    print(f"on/off state after cron: {state}")
    return on, off

def blink(led: IntEnum, blinks=6):
    for i in range(blinks):
        piglow.set(led, POWER)
        time.sleep(0.25)
        piglow.set(led, 0)
        time.sleep(0.25)

def blink_leg(leg: IntEnum, blinks= 6):
    for i in range(blinks):
        piglow.leg(leg, POWER)
        time.sleep(0.25)
        piglow.leg(leg, 0)
        time.sleep(0.25)
    

def leg_off(leg: IntEnum):
    piglow.arm(leg, 0)

def read_prev_state(fp: Path) -> Dict:
    """Return a dict holding each piglow arm's state on last run.

    Reads the given logfile for it's last line, only. At the moment,
    this state is just for LEG2- the 10-minutely result."""
    with open(str(fp), 'r') as f:
        try:  # catch OSError in case of a one line file 
            f.seek(-2, os.SEEK_END)
            while f.read(1) != b'\n':
                f.seek(-2, os.SEEK_CUR)
        except OSError:
            f.seek(0)
        last_line = f.readline()
   
    print(f"prev_state: {last_line}")

    try:
        prev_state = last_line.split("exit state:")[-1] 
        print(f"prev_state: {prev_state = }")
        prev_state = eval(last_line.split("exit state:")[-1])
        print(f"evaled state: {prev_state = }")
    except:
        prev_state = {"on": set(), "off": set()}
        print("no prev state found")
    return prev_state

# def get_gpio_state(res, trial) -> Dict:
#    """Return Cron (leg) state """
#
#    return state

if __name__ == "__main__":
    # read prior gpio state. there appears no direct hardware method
    # so storing in logfile on close is fastest to implement
    prev_state = read_prev_state(TEST_LOG)
    prev_on, prev_off = prev_state["on"], prev_state["off"]

    trial = (datetime.now().minute % 6) + 12  # add 12 to reach Cron value
    res = ping_router(ip=IP)
    animate_responses(res)
    on, off = animate_cron(res, trial)

    # log gpio state for later reload
    on = (prev_on | on ) - off
    print(f"exit state: {on = }, {off = }")
    logging.info(f"exit state: {on = }, {off = }")
