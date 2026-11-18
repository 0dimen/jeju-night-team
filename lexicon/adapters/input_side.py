def candidates(rows,limit=10):
    output={}
    for row in rows:
        group=output.setdefault(row['enum'],[])
        if len(group)<limit:
            group.append(row['term'])
    return output
