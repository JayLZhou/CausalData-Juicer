from tickets import open_ticket


def test_ticket_id_is_string():
    ticket = open_ticket(42, 'boom')
    assert ticket.ticket_id == '42'
    assert ticket.title == 'boom'


def test_sequence_of_tickets():
    ids = [open_ticket(n, 't').ticket_id for n in (1, 2, 3)]
    assert ids == ['1', '2', '3']
