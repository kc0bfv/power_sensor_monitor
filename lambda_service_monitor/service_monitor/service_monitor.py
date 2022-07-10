#!/usr/bin/env python3

import datetime as dt
import json
import os
import urllib.request
import urllib.error

from typing import Optional

import boto3

SETTINGS = None
def get_settings():
    global SETTINGS
    if SETTINGS is None:
        SETTINGS = dict()
        SETTINGS["region"] = os.environ.get("region")
        SETTINGS["profile"] = os.environ.get("profile")
        SETTINGS["from_addr"] = os.environ["email_from"]
        SETTINGS["url"] = os.environ["monitor_url"]
        SETTINGS["email_url"] = os.environ["email_url"]
        SETTINGS["diff_threshold"] = int(os.environ.get("diff_threshold", "10"))

        to_addr_s = os.environ["email_to"]
        to_addr_list = [s.strip() for s in to_addr_s.split(";") if s.strip() != ""]
        SETTINGS["to_addrs"] = to_addr_list
        SETTINGS["timeout"] = int(os.environ.get("timeout", "10"))
    return SETTINGS
    

def alert_failed(msg_txt: str = "Connection fail") -> None:
    settings = get_settings()
    subject = "ALERT: Power Sensor Monitor"
    body = f"URL: {settings['email_url']}\nMSG: {msg_txt}"

    sess = boto3.session.Session(region_name=settings["region"],
            profile_name=settings["profile"])
    ses = sess.client("ses")
    response = ses.send_email(
        Source = settings["from_addr"],
        Destination = {"ToAddresses": settings["to_addrs"]},
        Message = {
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body} },
        }
    )

    print(f"SES Response: {response}")

"""
Check the sensor data for no current flow, the power being out, or no sensor
return data recently.
"""
def check_data(raw_data_str: str):
    settings = get_settings()
    diffs_to_check = 4

    # Interpret the raw data
    # Many entries like:
    """
    {"published_at": "2022-02-14T03:42:08.865Z", "data": "39, 66, 478, 544, 0, 19, 98.062500, \"VIN\""}
    """
    # The data is humidity, temp, count, total, min, max, batt level, pwr source
    raw_data = json.loads(raw_data_str)

    # Grab the entries we're interested in - the last several entries
    raw_data_pts = raw_data[-diffs_to_check:]
    
    # Pull out just the data and published_at portions
    data_strs_unsplit = [i["data"] for i in raw_data_pts]
    published_ats = [i["published_at"] for i in raw_data_pts]
    
    # Split the data portion up by commas
    data_strs = [[a.strip() for a in dsu.split(",")] for dsu in data_strs_unsplit]

    # Grab the temp, min, max, and the power source separately
    data_temp = [int(ds[1]) for ds in data_strs]
    data_mins = [int(ds[4]) for ds in data_strs]
    data_maxs = [int(ds[5]) for ds in data_strs]
    data_on_vins = [ds[7] == '"VIN"' for ds in data_strs]

    # Find the temperatures below or at 32 - freezing
    low_temps = [temp for temp in data_temp if temp <= 32]

    # Calculate the differences between min and max
    data_diffs = [mx-mn for (mn, mx) in zip(data_mins, data_maxs)]

    # Keep only the differences greater than our on/off threshold
    big_diffs = [diff for diff in data_diffs if diff > settings["diff_threshold"]]

    # Strip the "Z" for zulu off the published_at times, then convert their times
    pub_at_with_z = [p for p in published_ats if p[-1] == "Z"]
    pub_at_removed_z = [p[:-1] for p in pub_at_with_z]
    pub_at_datetimes = [
        dt.datetime.fromisoformat(p).replace(tzinfo=dt.timezone.utc)
        for p in pub_at_removed_z
    ]

    # Get current time, determine difference from published times, keep the recent
    now = dt.datetime.now(dt.timezone.utc)
    all_pub_diffs = [now - pub_at for pub_at in pub_at_datetimes]
    recent_pubs = [d for d in all_pub_diffs if d < dt.timedelta(days=1)]

    # Build up alerts
    alerts = []

    # Alert if more than two of the checked entries are off
    # and if more than two of the temperatures are 32 or below
    if len(big_diffs) < (diffs_to_check - 2) and len(low_temps) > 2:
        alerts.append("Bulbs may be out")
    
    # Alert if not all the power entries are "VIN"
    if not all(data_on_vins):
        alerts.append("Power is off to the sensor")

    # Alert if some of the datetimes don't make sense
    if len(pub_at_with_z) < diffs_to_check:
        alerts.append(f"Invalid datetimes received: {published_ats}")

    # Alert if data is old
    if len(recent_pubs) < (diffs_to_check - 2):
        alerts.append("Sensor hasn't reported enough recent data")

    if len(alerts) > 0:
        alert_failed("\n".join(alerts))

    return True

# Return False or error if user needs to be notified about failure
def run_monitor():
    settings = get_settings()
    req = urllib.request.Request(settings["url"])
    try:
        with urllib.request.urlopen(req, timeout=settings["timeout"]) as urlf:
            data = urlf.read()
    except urllib.error.HTTPError as err:
        raise err
    else:
        return check_data(data)
    print("End of run monitor")
    return False

def service_monitor(event, context):
    try:
        if not run_monitor():
            alert_failed("Connection fail: returned false")
    except BaseException as e:
        alert_failed("Connection fail: {}".format(e))
        raise e
    except:
        alert_failed("Connection fail: non-BaseException?")
        raise
        

if __name__ == "__main__":
    service_monitor((),())
