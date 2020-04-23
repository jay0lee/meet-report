# Clone meet-report
git clone https://github.com/jay0lee/meet-report.git

# Install GAM, we'll use it to setup project and authorize
bash <(curl -s -S -L https://git.io/install-gam)

GAM=~/bin/gam/gam
MEETREPORT=~/meet-report/
OAUTHFILE=$MEETREPORT/oauth2.txt
CLIENTSECRETS=$MEETREPORT/client_secrets.json

$gam use project $GOOGLE_CLOUD_PROJECT

read -p "Enter your admin email address: " ADMINUSER

SCOPES="https://www.googleapis.com/auth/gmail.send,https://www.googleapis.com/auth/admin.reports.audit.readonly,https://www.googleapis.com/auth/calendar.events.readonly
,email"
$gam create oauth $ADMINUSER $SCOPES

cp $MEETREPORT/config.py.example $MEETREPORT/config.py

gcloud app deploy $MEETREPORT --quiet
gcloud app deploy $MEETREPORT/cron.yaml --quiet
