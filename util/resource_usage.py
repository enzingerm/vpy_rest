from datetime import datetime, timedelta

# [start     [      ]         [  ]            [   ]                [     |5min       ]                    now]
#               ^               ^               ^
# marked intervals can be merged into total usage time
#


class ResourceUsage:
    def __init__(self):
        self.used_timespans = []
        self.started_at = None
        self.used_time = timedelta()

    def start(self):
        assert not self.started()
        self.started_at = datetime.now()

    def started(self):
        return self.started_at is not None

    def is_currently_used(self):
        return len(self.used_timespans) > 0 and self.used_timespans[-1][1] is None

    def start_using(self):
        assert not self.is_currently_used()
        if not self.started():
            self.start()
        self.used_timespans.append([datetime.now(), None])

    def stop_using(self):
        assert self.is_currently_used()
        timespan = self.used_timespans[-1]
        timespan[1] = datetime.now()

    def get_used_fraction(self):
        assert self.started()
        self.merge_older_5min()
        now = datetime.now()
        timespan = now - self.started_at
        return (
            self.used_time
            + sum((((e or now) - s) for (s, e) in self.used_timespans), timedelta())
        ) / timespan

    def get_used_fraction_5min(self):
        assert self.started()
        self.merge_older_5min()
        now = datetime.now()
        timespan = min(now - self.started_at, timedelta(minutes=5))
        start = now - timespan
        # now sum up all the intervals
        return (
            sum(
                (
                    ((e or now) - (s if s > start else start))
                    for (s, e) in self.used_timespans
                ),
                timedelta(),
            )
            / timespan
        )

    def merge_older_5min(self):
        now = datetime.now()
        for start, end in self.used_timespans:
            if end is None or now - timedelta(minutes=5) < end:
                break
            self.used_time += end - start
            self.used_timespans = self.used_timespans[1:]
