SRC := service_monitor/service_monitor.py
OUT_ZIP := service_monitor.zip

${OUT_ZIP}: ${SRC}
	zip -j -u "$@" "$<"

test:
	mypy "${SRC}"
