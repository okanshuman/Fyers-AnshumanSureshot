# Login.py

import Credentails as cr
from fyers_apiv3 import fyersModel

grant_type = "authorization_code"  ## The grant_type always has to be "authorization_code"
response_type = "code"  ## The response_type always has to be "code"
state = "sample"

appSession = fyersModel.SessionModel(client_id=cr.client_id, redirect_uri=cr.redirect_uri, response_type=response_type,
                                     state=state, secret_key=cr.secret_key, grant_type=grant_type)

from datetime import datetime, timedelta, date
from time import sleep
import os
import pyotp
import requests
from urllib.parse import parse_qs, urlparse
import warnings
import pandas as pd

pd.set_option('display.max_columns', None)
warnings.filterwarnings('ignore')

import base64

def getEncodedString(string):
    string = str(string)
    base64_bytes = base64.b64encode(string.encode("ascii"))
    return base64_bytes.decode("ascii")


URL_SEND_LOGIN_OTP = "https://api-t2.fyers.in/vagator/v2/send_login_otp_v2"
res = requests.post(url=URL_SEND_LOGIN_OTP, json={"fy_id": getEncodedString(cr.FY_ID), "app_id": "2"}).json()
#print(res)

if datetime.now().second % 30 > 27: sleep(5)
URL_VERIFY_OTP = "https://api-t2.fyers.in/vagator/v2/verify_otp"
res2 = requests.post(url=URL_VERIFY_OTP,
                     json={"request_key": res["request_key"], "otp": pyotp.TOTP(cr.TOTP_KEY).now()}).json()
#print(res2)

ses = requests.Session()
URL_VERIFY_OTP2 = "https://api-t2.fyers.in/vagator/v2/verify_pin_v2"
payload2 = {"request_key": res2["request_key"], "identity_type": "pin", "identifier": getEncodedString(cr.PIN)}
res3 = ses.post(url=URL_VERIFY_OTP2, json=payload2).json()
#print(res3)

ses.headers.update({
    'authorization': f"Bearer {res3['data']['access_token']}"
})

TOKENURL = "https://api-t1.fyers.in/api/v3/token"
payload3 = {"fyers_id": cr.FY_ID,
            "app_id": cr.client_id[:-4],
            "redirect_uri": cr.redirect_uri,
            "appType": "100", "code_challenge": "",
            "state": "None", "scope": "", "nonce": "", "response_type": "code", "create_cookie": True}

res3 = ses.post(url=TOKENURL, json=payload3).json()
#print(res3)

url = res3['Url']
print(url)
parsed = urlparse(url)
auth_code = parse_qs(parsed.query)['auth_code'][0]
#auth_code

grant_type = "authorization_code"
response_type = "code"
session = fyersModel.SessionModel(
    client_id=cr.client_id,
    secret_key=cr.secret_key,
    redirect_uri=cr.redirect_uri,
    response_type=response_type,
    grant_type=grant_type
)

session.set_token(auth_code)
response = session.generate_token()
#print(response)

access_token = response['access_token']
#print("access_token: "+ access_token)
fyers_active = fyersModel.FyersModel(client_id=cr.client_id, is_async=False, token=access_token, log_path=os.getcwd())

#print (fyers_active.get_profile())
