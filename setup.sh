# Clone meet-report
git clone https://github.com/jay0lee/meet-report.git
cd meet-report
git pull
cd ~

# Install GAM wihthout setup, we'll use it to setup project and authorize
bash <(curl -s -S -L https://git.io/install-gam) -l

GAMPATH=~/bin/gam/
GAM=$GAMPATH/gam
MEETREPORT=~/meet-report/

read -p "Enter your admin email address: " ADMINUSER

cp $MEETREPORT/project-apis.txt $GAMPATH

BUILDURL="https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com?project=$GOOGLE_CLOUD_PROJECT"
until $GAM use project $ADMINUSER $GOOGLE_CLOUD_PROJECT; do
  echo "Please go to:"
  echo ""
  echo "$BUILDURL"
  echo ""
  echo "and enable the Cloud Build API. Note that you'll need to setup Billing to do so."
  echo ""
  read -p "Press enter when done." done
done

SCOPES="https://www.googleapis.com/auth/gmail.send,https://www.googleapis.com/auth/admin.reports.audit.readonly,https://www.googleapis.com/auth/calendar.events.readonly,email"
$GAM oauth create admin $ADMINUSER scopes $SCOPES
cp $GAMPATH/oauth2.txt $MEETREPORT

cp $MEETREPORT/config.py.example $MEETREPORT/config.py

gcloud app create
gcloud app deploy $MEETREPORT --quiet
gcloud app deploy $MEETREPORT/cron.yaml --quiet
