import gspread
from google.oauth2.service_account import Credentials
import toml

secrets = toml.load('.streamlit/secrets.toml')
creds_dict = dict(secrets['gcp_service_account'])
creds = Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive'])
client = gspread.authorize(creds)
ss = client.open_by_url('https://docs.google.com/spreadsheets/d/1wiHjqcHGvENIZBSsrm85RkcoFgy3HCMnoYOCvxRD2aI/edit')
ws = ss.worksheet('シート1')
ws.clear()
print('Sheet cleared. A1 value:', repr(ws.acell('A1').value))
