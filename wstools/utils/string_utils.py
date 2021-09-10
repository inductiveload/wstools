

def combine_list(items, final_joiner="and"):

    if len(items) > 1:
        text = ", ".join(items[:-1]) + " " + final_joiner + " " + items[-1]
    elif len(items):
        text = items[0]
    else:
        text = ""

    return text
