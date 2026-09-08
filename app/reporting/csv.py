import csv
import io
from datetime import date, datetime

from fastapi.responses import Response


def csv_response(filename, columns, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        values = []
        for key in columns:
            value = row.get(key)
            if isinstance(value, (date, datetime)):
                value = value.isoformat()
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            values.append("" if value is None else value)
        writer.writerow(values)
    return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"',
                             "Cache-Control": "no-store"})
