#!/usr/bin/env python3

import json
import os
import urllib.request
import urllib.error

import boto3

def alert_failed(msg_txt="Connection fail"):
    region = os.environ.get("region")
    profile = os.environ.get("profile")
    from_addr = os.environ["email_from"]
    to_addr = os.environ["email_to"]
    subject = "ALERT: Power Sensor Monitor"

    sess = boto3.session.Session(region_name=region, profile_name=profile)
    ses = sess.client("ses")
    response = ses.send_email(
        Source = from_addr,
        Destination = {"ToAddresses": [to_addr]},
        Message = {
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": msg_txt} },
        }
    )

    print(f"SES Response: {response}")

def check_data(raw_data_str):
    diff_threshold = int(os.environ.get("diff_threshold", "15"))
    diffs_to_check = 4

    raw_data = json.loads(raw_data_str)
    raw_data_pts = raw_data[-diffs_to_check:]
    data_strs_unsplit = [i["data"] for i in raw_data_pts]
    data_strs = [[a.strip() for a in dsu.split(",")] for dsu in data_strs_unsplit]
    data_mins = [int(ds[4]) for ds in data_strs]
    data_maxs = [int(ds[5]) for ds in data_strs]
    data_on_vins = [ds[7] == '"VIN"' for ds in data_strs]

    data_diffs = [mx-mn for (mn, mx) in zip(data_mins, data_maxs)]
    big_diffs = [diff for diff in data_diffs if diff > diff_threshold]

    alerts = []

    if len(big_diffs) < (diffs_to_check - 2):
        alerts.append("Bulbs may be out")
    
    if not all(data_on_vins):
        alerts.append("Power is off to the sensor")

    if len(alerts) > 0:
        alert_failed("\n".join(alerts))

    return True

# Return False or error if user needs to be notified about failure
def run_monitor():
    url = os.environ["monitor_url"]
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=1) as urlf:
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
