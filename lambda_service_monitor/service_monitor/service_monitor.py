#!/usr/bin/env python3

import datetime as dt
import json
import os
import urllib.request
import urllib.error

from typing import Optional

import boto3

"""
Send email alerts using AWS SES.  Use environment variables for the
default region, profile, email_from address and email_to address.
All emails have the same subject - provided upon init.
"""
class EmailAlerter:
    def __init__(self, subject: str, region: Optional[str] = None,
            profile: Optional[str] = None, from_addr: Optional[str] = None,
            to_addr: Optional[str] = None):
        region_s = os.environ.get("region") if region is None else region
        profile_s = os.environ.get("profile") if profile is None else profile
        from_addr_s = os.environ["email_from"] if from_addr is None else from_addr
        to_addr_s = os.environ["email_to"] if to_addr is None else to_addr

        self.subject: str = subject
        self.region: Optional[str] = region_s
        self.profile: Optional[str] = profile_s
        self.from_addr: Optional[str] = from_addr_s
        self.to_addr: Optional[str] = to_addr_s

    def send_email(self, msg_txt: str):
        sess = boto3.session.Session(region_name=self.region, profile_name=self.profile)
        ses = sess.client("ses")
        response = ses.send_email(
            Source = self.from_addr,
            Destination = {"ToAddresses": [self.to_addr]},
            Message = {
                "Subject": {"Data": self.subject},
                "Body": {"Text": {"Data": msg_txt} },
            }
        )

        print(f"SES Response: {response}")

"""
Check the sensor data for no current flow, the power being out, or no sensor
return data recently.
"""
def check_data(emailer: EmailAlerter, raw_data_str: str):
    diff_threshold = int(os.environ.get("diff_threshold", "10"))
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

    # Grab the min, max, and the power source separately
    data_mins = [int(ds[4]) for ds in data_strs]
    data_maxs = [int(ds[5]) for ds in data_strs]
    data_on_vins = [ds[7] == '"VIN"' for ds in data_strs]

    # Calculate the differences between min and max
    data_diffs = [mx-mn for (mn, mx) in zip(data_mins, data_maxs)]

    # Keep only the differences greater than our on/off threshold
    big_diffs = [diff for diff in data_diffs if diff > diff_threshold]

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
    if len(big_diffs) < (diffs_to_check - 2):
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
        emailer.send_email("\n".join(alerts))

    return True

# Return False or error if user needs to be notified about failure
def run_monitor(emailer: EmailAlerter):
    url = os.environ["monitor_url"]
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=1) as urlf:
            data = urlf.read()
    except urllib.error.HTTPError as err:
        raise err
    else:
        return check_data(emailer, data)
    print("End of run monitor")
    return False

def service_monitor(event, context):
    emailer = EmailAlerter("ALERT: Power Sensor Monitor")

    try:
        if not run_monitor(emailer):
            emailer.send_email("Connection fail: returned false")
    except BaseException as e:
        emailer.send_email("Connection fail: {}".format(e))
        raise e
    except:
        emailer.send_email("Connection fail: non-BaseException?")
        raise
        

if __name__ == "__main__":
    service_monitor((),())
