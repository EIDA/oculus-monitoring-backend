"""Formatter module for logging consistency-check results."""     

def format_result(idx, url, available, ds_result, match):
    net = match["network"]
    sta = match["station"]
    cha = match["channel"]
    loc = match.get("location", "")

    original_start = match.get("starttime", "?")
    original_end = match.get("endtime", "?")

    log = [f"{idx}. {url}"]

        # Availability result
    if available:
        line = "     Availability: ✅ (timespan covered)"
        matched_span = match.get("matched_span")
        if matched_span:
            line += f" → {matched_span['start']} → {matched_span['end']}"
        log.append(line)
    else:
        log.append("     Availability: ❌ (No availability in this timespan)")


    # Dataselect result
    dataselect_status = "✅" if ds_result["success"] else f"❌ ({ds_result['status']})"
    log.append(f"     Dataselect:   {dataselect_status}")

    consistent = available == ds_result["success"]
    log.append(f"     Consistent:   {'✅' if consistent else '❌'}")
    log.append(f"     Epoch span: {original_start} → {original_end}")

    debug = ds_result.get("debug", "").strip()
    if debug:
        log.append(debug)

    return "\n".join(log)
