from pydantic import BaseModel


class Ticket(BaseModel):
    ticket_id: str
    title: str


def open_ticket(seq_no, title):
    # seq_no arrives as an int from the sequence generator
    return Ticket(ticket_id=seq_no, title=title)
