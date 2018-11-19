import codecs
from io import StringIO
from django.utils.encoding import smart_text
import csv


class Echo(object):
    """An object that implements just the write method of the file-like
    interface.
    """
    def write(self, value):
        """Write the value by returning it, instead of storing in a buffer."""
        return value


class UnicodeWriter(object):
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = StringIO()
        self.writer = csv.DictWriter(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()
        self.writer.writeheader()

    def writerow(self, row):
        self.writer.writerow({k: smart_text(s)
                              for k, s in row.items()})
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        # reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        res = self.stream.write(data)
        # empty queue
        self.queue.truncate(0)
        return res

    def writerows(self, rows):
        for row in rows:
            yield self.writerow(row)
