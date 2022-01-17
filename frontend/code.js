window.DEBUG = true;

$(document).ready(main);

function main() {
    const read_key = get_read_key();
    get_data(read_key, data_handler);
}

function debug_log() {
    if( window.DEBUG === true ) { console.log.apply(null, arguments); }
}

function get_read_key() {
    return window.location.hash.slice(1);
}

function get_data(read_key, result_handler) {
    const jsonsrc = "http://169.197.131.226:8080/webhook/get/" + read_key;
    //const jsonsrc = "http://192.168.86.11:8080/webhook/get/" + read_key;
    $.getJSON(jsonsrc, result_handler)
        .fail(function() { alert("Failed to get data..."); })
}

function data_handler(in_data) {
    debug_log(in_data);

    const pub_at = sel_elem_list("published_at", in_data);
    const data = map_list(trim_list, split_list(",", sel_elem_list("data", in_data)));

    const labels = build_label_list(pub_at);
    const humid = num_list(sel_elem_list(0, data));
    const tempf = num_list(sel_elem_list(1, data));
    const count = num_list(sel_elem_list(2, data));
    const total = num_list(sel_elem_list(3, data));
    const min = num_list(sel_elem_list(4, data));
    const max = num_list(sel_elem_list(5, data));
    const batt = num_list(sel_elem_list(6, data));

    function make_vin_one(elem) {
        return elem == "\"VIN\"" ? 1 : 0;
    }
    const pwr_src = map_list(make_vin_one, sel_elem_list(7, data));

    const power_diff = abs_list(diff_list(min, max));

    const last_pwr_diff = power_diff.slice(-1)[0];
    const last_status = last_pwr_diff > 10 ? "ON" : "OFF";
    document.getElementById("last_power_status").innerText = last_status;

    const pwr_diff_chart = new Chart(
        document.getElementById("pwr_diff_chart"),
        {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                        label: "Power Difference",
                        data: power_diff
                }]
            },
            options: {}
        }
    );

    const pwr_src_chart = new Chart(
        document.getElementById("pwr_src_chart"),
        {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                        label: "Power Source - 1 means electricity is on to unit",
                        data: pwr_src
                }]
            },
            options: {}
        }
    );

    const temp_humid_chart = new Chart(
        document.getElementById("temp_humid_chart"),
        {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Temperature (F)",
                        data: tempf,
                        borderColor: "rgb(255, 0, 0)",
                    },
                    {
                        label: "Humidity (%)",
                        data: humid,
                        borderColor: "rgb(0, 0, 255)",
                    },
                ]
            },
            options: {}
        }
    );
}

function sel_elem_list(to_sel, in_list) {
    return in_list.map( function (elem) { return elem[to_sel]; } );
}

function num_list(in_list) {
    return in_list.map( function (elem) { return Number(elem); } );
}

function diff_list(list_1, list_2) {
    return list_1.map( function (elem, ind) { return elem - list_2[ind]; } );
}

function abs_list(in_list) {
    return in_list.map( function (elem) { return Math.abs(elem); } );
}

function split_list(splitpt, in_list) {
    return in_list.map( function (elem) { return elem.split(splitpt); } );
}

function trim_list(in_list) {
    return in_list.map( function (elem) { return elem.trim(); } );
}

function map_list(map_func, in_list) {
    return in_list.map( function (elem) { return map_func(elem); } );
}

function build_label_list(in_list) {
    return in_list.map( function (elem) {
        const split = elem.split("T");
        const date = split[0];
        const time = split[1];

        const dsplit = date.split("-");
        const year = dsplit[0];
        const month = dsplit[1];
        const day = dsplit[2];

        const tsplit = time.split(":");
        const hr = tsplit[0];
        const min = tsplit[1];
        const sec_zone = tsplit[2];

        const zone = sec_zone.slice(-1);
        const sec = sec_zone.slice(0, -1);

        return `${month}/${day} ${hr}:${min}`;
    });
}
