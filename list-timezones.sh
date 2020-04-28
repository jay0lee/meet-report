pycode='import pytz
for tz in pytz.all_timezones:
  print(tz)'

python3 -c "${pycode}" | less
