$(function() {
    var dataReceived = []
    function newEventSource(url, onopen, onmessage, onerror) {
        var es = new EventSource(url)
        es.onopen = onopen
        es.onmessage = onmessage
        es.onerror = onerror
    }

    function convertToCSV(objArray) {
        const array = [Object.keys(objArray[0])];
        objArray.forEach(obj => {
        array.push(Object.values(obj));
        });
        return array.map(row => row.join(',')).join('\n');
    }

    function downloadCSV(objArray, filename = 'data.csv') {
        const csv = convertToCSV(objArray);
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
    $("button#download-btn").on("click", function(ev) {
        ev.preventDefault()
        if (dataReceived.length > 0) {
            downloadCSV(dataReceived, 'facebook_links.csv')
        }
    })
    $("form#search-form").on("submit", function(event) {
        event.preventDefault()
        event.stopPropagation()
        const $thisForm = $(this)
        console.log("This form:", $thisForm)
        const formData = new FormData($thisForm.get(0));
        q = formData.get("q")
        if (!q) {
            alert("fill in search box");
            return;
        }
        const url = new URL("/search", window.location.origin)
        url.searchParams.set("q", q.toString())
        $thisForm.prop("disabled", true);
        $thisForm.find("input").prop("disabled", true);
        $thisForm.find("button").prop("disabled", true);
        $("button#download-btn").prop("disabled", true);
        dataReceived = []
        $("table#result-table tbody").empty().append($(`<tr><td colspan="2">Loading.. Please Wait</td></tr>`))
        newEventSource(
            url,
            function(ev) {  // on open
                console.log("Connected")
            },
            function(ev) {  // on message
                var msg = ev.data
                try {
                    msg = JSON.parse(msg)
                    if (Object.hasOwn(msg, "error")) {
                        throw new Error(msg["error"])
                    } else if (Object.hasOwn(msg, "processing")) {
                        console.log("processing....")
                    } else if (Object.hasOwn(msg, "done")) {
                        console.log("Result:")
                        console.log(msg["done"])
                        $("table#result-table tbody").empty();
                        let trs = []
                        msg['done'].forEach(({ Title, Link }) => {
                            let $tr = $("<tr>");
                            $tr.append($(`<td><p class="text-wrap text-break">${Title}</p></td>`));
                            $tr.append($(`<td><p class="text-wrap text-break">${Link}</p></td>`));
                            trs.push($tr)
                        })
                        $("table#result-table tbody").append(trs);
                        $("button#download-btn").prop("disabled", false);
                        dataReceived = msg["done"];
                    } else {
                        console.log("exitted..")
                        this.close()
                        $thisForm.prop("disabled", false)
                        $thisForm.find("input").prop("disabled", false);
                        $thisForm.find("button").prop("disabled", false);
                        if ($("table#result-table tbody tr td[colspan=2]").text() == "Loading.. Please Wait") {
                            $("table#result-table tbody").empty().append($(`<tr><td colspan="2">No Data</td></tr>`));
                        }
                    }
                } catch(e) {
                    console.log("Error message:", e)
                }
            },
            function(ev) {  // on error
                console.log("disconnected error")
                $thisForm.prop("disabled", false)
                $thisForm.find("input").prop("disabled", false);
                $thisForm.find("button").prop("disabled", false);
            }
        )
    })
})