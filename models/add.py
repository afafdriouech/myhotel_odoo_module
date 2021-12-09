from odoo import models, fields, api, exceptions
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as dt


class reservation:

    client_order_id = fields.Many2one('res.partner', 'Ordering Contact',readonly=True,
                                       states={'draft': [('readonly', False)]},
                                       help="The name and address of the "
                                            "contact that requested the order or quotation.")
    folio_id = fields.Many2many('hotel.folio', 'hotel_folio_reservation_rel', 'order_id', 'invoice_id', string='Folio')
    no_of_folio = fields.Integer('Folio', compute="_compute_folio_id")
    dummy = fields.Datetime('Dummy')

@api.multi
def _compute_folio_id(self):
        folio_list = []
        for res in self:
            for folio in res.folio_id:
                folio_list.append(folio.id)
            folio_len = len(folio_list)
            res.no_of_folio = folio_len
        return folio_len

@api.onchange('client_id')
def onchange_partner_id(self):
    '''
    When you change partner_id it will update the partner_invoice_id,
    partner_shipping_id and pricelist_id of the hotel reservation as well
    ---------------------------------------------------------------------
    @param self: object pointer
    '''
    if not self.client_id:
        self.client_invoice_id = False
        self.client_order_id = False
    else:
        addr = self.client_id.address_get(['delivery', 'invoice',
                                            'contact'])
        self.client_invoice_id = addr['invoice']
        self.client_order_id = addr['contact']


@api.multi
def create_folio(self):
        """
        This method is for create new hotel folio.
        -----------------------------------------
        @param self: The object pointer
        @return: new record set for hotel folio.
        """
        hotel_folio_obj = self.env['myhotel.folio']
        room_obj = self.env['myhotel.chambre']
        for reservation in self:
            folio_lines = []
            checkin_date = reservation['checkin']
            checkout_date = reservation['checkout']
            if not self.checkin < self.checkout:
                raise exceptions.ValidationError('Checkout date should be greater \
                                         than the Check-in date.')
            duration_vals = (self.onchange_check_dates
                             (checkin_date=checkin_date,
                              checkout_date=checkout_date, duration=False))
            duration = duration_vals.get('duration') or 0.0
            folio_vals = {
                'date_order': reservation.date_order,
                'client_id': reservation.client_id.id,
                'partner_invoice_id': reservation.partner_invoice_id.id,
                'checkin_date': reservation.checkin,
                'checkout_date': reservation.checkout,
                'duration': duration,
                'reservation_id': reservation.id,
                #'service_lines': reservation['folio_id']
            }
            for line in reservation.reservation_line:
                for r in line.reserve:
                    folio_lines.append((0, 0, {
                        'checkin_date': checkin_date,
                        'checkout_date': checkout_date,
                        'product_id': r.product_id and r.product_id.id,
                        'name': reservation['reservation_no'],
                        'price_unit': r.list_price,
                        'product_uom_qty': duration,
                        'is_reserved': True}))
                    res_obj = room_obj.browse([r.id])
                    res_obj.write({'status': 'occupied', 'isroom': False})
            folio_vals.update({'room_lines': folio_lines})
            folio = hotel_folio_obj.create(folio_vals)
            if folio:
                for rm_line in folio.room_lines:
                    rm_line.product_id_change()
            self._cr.execute('insert into hotel_folio_reservation_rel'
                             '(order_id, invoice_id) values (%s,%s)',
                             (reservation.id, folio.id))
            self.state = 'done'
        return True


###########################

class HotelFolio(models.Model):

    @api.multi
    def name_get(self):
        res = []
        disp = ''
        for rec in self:
            if rec.order_id:
                disp = str(rec.name)
                res.append((rec.id, disp))
        return res

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        args += ([('name', operator, name)])
        mids = self.search(args, limit=100)
        return mids.name_get()

    @api.model
    def _get_checkin_date(self):
        if self._context.get('tz'):
            to_zone = self._context.get('tz')
        else:
            to_zone = 'UTC'
        return _offset_format_timestamp1(time.strftime("%Y-%m-%d 12:00:00"),
                                         DEFAULT_SERVER_DATETIME_FORMAT,
                                         DEFAULT_SERVER_DATETIME_FORMAT,
                                         ignore_unparsable_time=True,
                                         context={'tz': to_zone})

    @api.model
    def _get_checkout_date(self):
        if self._context.get('tz'):
            to_zone = self._context.get('tz')
        else:
            to_zone = 'UTC'
        tm_delta = datetime.timedelta(days=1)
        return datetime.datetime.strptime(_offset_format_timestamp1
                                          (time.strftime("%Y-%m-%d 12:00:00"),
                                           DEFAULT_SERVER_DATETIME_FORMAT,
                                           DEFAULT_SERVER_DATETIME_FORMAT,
                                           ignore_unparsable_time=True,
                                           context={'tz': to_zone}),
                                          '%Y-%m-%d %H:%M:%S') + tm_delta

    @api.multi
    def copy(self, default=None):
        return super(HotelFolio, self).copy(default=default)

    _name = 'myhotel.folio'
    _description = 'hotel folio new'
    _rec_name = 'order_id'
    _order = 'id'

    name = fields.Char('Folio Number', readonly=True, index=True, default='New')
    order_id = fields.Many2one('sale.order', 'Order', delegate=True,
                               required=True, ondelete='cascade')
    checkin_date = fields.Datetime('Check In', required=True, readonly=True,
                                   states={'draft': [('readonly', False)]},
                                   default=_get_checkin_date)
    checkout_date = fields.Datetime('Check Out', required=True, readonly=True,
                                    states={'draft': [('readonly', False)]},
                                    default=_get_checkout_date)
    room_lines = fields.One2many('myhotel.folio.line', 'folio_id',
                                 readonly=True,
                                 states={'draft': [('readonly', False)],
                                         'sent': [('readonly', False)]},
                                 help="Hotel room reservation detail.")
    #service_lines = fields.One2many('hotel.service.line', 'folio_id',readonly=True,
                                    #states={'draft': [('readonly', False)],'sent': [('readonly', False)]},
                                    #help="Hotel services details provided to Customer and it will included in the main Invoice.")
    hotel_policy = fields.Selection([('prepaid', 'On Booking'),
                                     ('manual', 'On Check In'),
                                     ('picking', 'On Checkout')],
                                    'Hotel Policy', default='manual',
                                    help="Hotel policy for payment that "
                                    "either the guest has to payment at "
                                    "booking time or check-in "
                                    "check-out time.")
    duration = fields.Float('Duration in Days',
                            help="Number of days which will automatically "
                            "count from the check-in and check-out date. ")
    hotel_invoice_id = fields.Many2one('account.invoice', 'Invoice', copy=False)
    duration_dummy = fields.Float('Duration Dummy')

    @api.constrains('room_lines')
    def folio_room_lines(self):
        '''
        This method is used to validate the room_lines.
        ------------------------------------------------
        @param self: object pointer
        @return: raise warning depending on the validation
        '''
        folio_rooms = []
        for room in self[0].room_lines:
            if room.product_id.id in folio_rooms:
                raise ValidationError(_('vous pouvez pas prendre la meme chambre 2 fois'))
            folio_rooms.append(room.product_id.id)

    @api.onchange('checkout_date', 'checkin_date')
    def onchange_dates(self):
                '''
                if customer will leave only for some hour it would be considers
                as a whole day.
                '''
                configured_addition_hours = 5
                myduration = 0
                chckin = self.checkin_date
                chckout = self.checkout_date
                if chckin and chckout:
                    server_dt = DEFAULT_SERVER_DATETIME_FORMAT
                    chkin_dt = datetime.datetime.strptime(chckin, server_dt)
                    chkout_dt = datetime.datetime.strptime(chckout, server_dt)
                    dur = chkout_dt - chkin_dt
                    sec_dur = dur.seconds
                    if (not dur.days and not sec_dur) or (dur.days and not sec_dur):
                        myduration = dur.days
                    else:
                        myduration = dur.days + 1
                    # To calculate additional hours in hotel room as per minutes
                    if configured_addition_hours > 0:
                        additional_hours = abs((dur.seconds / 60) / 60)
                        if additional_hours >= configured_addition_hours:
                            myduration += 1
                self.duration = myduration
                self.duration_dummy = self.duration



class HotelFolioLine(models.Model):

    @api.multi
    def copy(self, default=None):
        '''
        @param self: object pointer
        @param default: dict of default values to be set
        '''
        return super(HotelFolioLine, self).copy(default=default)

    @api.model
    def _get_checkin_date(self):
        if 'checkin' in self._context:
            return self._context['checkin']
        return time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    @api.model
    def _get_checkout_date(self):
        if 'checkout' in self._context:
            return self._context['checkout']
        return time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    _name = 'myhotel.folio.line'
    _description = 'hotel folio1 room line'

    order_line_id = fields.Many2one('sale.order.line', string='Order Line',
                                    required=True, delegate=True,
                                    ondelete='cascade')
    folio_id = fields.Many2one('myhotel.folio', string='Folio',
                               ondelete='cascade')
    checkin_date = fields.Datetime('Check In', required=True,
                                   default=_get_checkin_date)
    checkout_date = fields.Datetime('Check Out', required=True,
                                    default=_get_checkout_date)
    is_reserved = fields.Boolean('Is Reserved',
                                 help='True when folio line created from \
                                 Reservation')
