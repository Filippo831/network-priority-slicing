from ryu.controller import event

class MonitorEvent(event.EventBase):
    def __init__(self, data):
        super(MonitorEvent, self).__init__()
        self.data = data
