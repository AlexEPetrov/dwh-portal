import ast
import datetime


# converters for pytest-bdd steps

def empty_to_none(value):
    return None if value.strip() == "-" else value

def to_optional_date(value):
    return None if value.strip() == "-" else datetime.datetime.strptime(value, "%Y-%m-%d").date()

def to_optional_int(value):
    return None if value.strip() == "-" else int(value)

def to_optional_float(value):
    return None if value.strip() == "-" else float(value)


def convert_table(table_text):
    rows = [line.strip() for line in table_text.split('\n') if line.strip()]
    headers = [h.strip() for h in rows[0].split('|')[1:-1]]
    data = []
    for row in rows[1:]:
        values = [ast.literal_eval(v.strip()) if v.strip() else None 
                 for v in row.split('|')[1:-1]]
        data.append(dict(zip(headers, values)))
    return data

def convert_dict(dict_text):
    return ast.literal_eval(dict_text)


def parse_str_table(table_with_headers):
    list_table_rows = table_with_headers.split("\n")
    list_headers = str(list_table_rows[0]).strip("|").split("|")
    dict_table = {}
    for header in list_headers:
        header_text = header.strip()
        lst_row = []
        for i in range(1, list_table_rows.__len__()):
            list_temp = list_table_rows[i].strip("|").split("|")
            lst_row.append(list_temp[list_headers.index(header)].strip())

        dict_table[header_text] = lst_row

    return dict_table