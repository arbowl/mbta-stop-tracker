pyinstaller -F -i=./icon.ico mbta_stop_tracker.pyw
xcopy api_key.env dist\ /Y
xcopy icon.ico dist\ /Y