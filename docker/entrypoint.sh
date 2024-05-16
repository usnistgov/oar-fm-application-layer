#! /bin/bash
#
port=9092
script=/dev/oar-fm-application-api/python/fm-application-api/run.py
[ -f "$script" ] || script=/app/dist/fm-application-api/bin/run.py

[ -n "$OAR_WORKING_DIR" ] || OAR_WORKING_DIR=`mktemp --tmpdir -d _fm-application-api.XXXXX`
[ -d "$OAR_WORKING_DIR" ] || {
    echo npsserver: ${OAR_WORKING_DIR}: working directory does not exist
    exit 10
}
[ -n "$OAR_LOG_DIR" ] || export OAR_LOG_DIR=$OAR_WORKING_DIR

echo
echo Working Dir: $OAR_WORKING_DIR
echo Access the MIDAS web services at http://localhost:$port/
echo


echo '++' uwsgi --plugin python3 --http-socket :$port --wsgi-file $script  \
                --set-ph oar_working_dir=$OAR_WORKING_DIR $opts
uwsgi --plugin python3 --http-socket :$port --wsgi-file $script --static-map /docs=/docs \
      --set-ph oar_working_dir=$OAR_WORKING_DIR $opts