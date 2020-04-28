# Meet Report
Meet Report is a [Google AppEngine](https://cloud.google.com/appengine) app that runs entirely in the Cloud and sends email reports to organizers and/or attendees of [Google Meet](https://gsuite.google.com/products/meet/) meetings. The report shows who attended, the time(s) they attended, how they joined (web browser, app, phone, etc) and optionally their IP address and geo location (these are reported for members of your G Suite domain only).

Here's a sample report:

![Meet Report Sample](https://github.com/jay0lee/meet-report/blob/master/meet-report-sample.png)

# Deploying Meet Report
Meet report is designed to run on Google AppEngine. You can deploy Meet Report for your G Suite domain with only a web browser. Here are the steps:
1. Go to https://console.cloud.google.com/cloud-resource-manager. Make sure your G Suite super admin account is showing at the top right of the screen, if it isn't log out of all other Google Accounts and login to the super admin account.
1. Create a new project.
1. Give your project a descriptive name and ID. I suggest something like meet-report-yourdomain-com
1. Once the project is created select it at the top right. The project name should now show in the project selection box at the top of the screen, just right of "Google Cloud Platform".
1. Open [Google Cloud Shell](https://cloud.google.com/shell) by clicking the `>_` icon at the top right of the Cloud Console window.
1. The project you just created should be selected in Cloud Shell, if it is, it will show in parenthesis and yellow text at the Cloud Shell prompt. If your new project is not currently selected you can run ```gcloud projects list``` to see project IDs and ```gcloud config set project <project-id>``` to select the correct project.
1. With the correct project selected, run: ```bash <(curl -s -S -L https://git.io/meet-report)``` to begin the Meet Report setup process.
1. The setup script will download the Meet Report app and begin configuring it. It uses [GAM](https://git.io/gam) to further configure your project so GAM is downloaded also. Follow the prompts to finish setup and installation.
1. Once the script is done Meet Report should be installed for your domain with some sane [default settings](https://raw.githubusercontent.com/jay0lee/meet-report/master/config.py.example). However, you can always edit these defaults. Run ```editor ~/meet-report/config.py``` to make changes to your config file and once saved, run ```gcloud app deploy meet-report``` to deploy the new config to AppEngine.
1. To confirm Meet Report is working, start your own [Google Meet](https://meet.google.com). By default, Meet Report only sends reports to the meeting organizer and only if 2 people joined and the meeting lasted longer than a minute (these defaults can be changed in config.py, see above step). Make sure your test meeting meets these requirements (invite another account, wait 1 minute). Meet Report runs every 30 minutes and waits about an hour before reporting on meetings to ensure they are done. You'll need to wait 1-2 hours before you see your Meet Report email.

