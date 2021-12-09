from odoo import models, fields, api, exceptions
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as dt


class reservation:
    pricelist_id = fields.Many2one('product.pricelist', 'Scheme',
                                   required=True, readonly=True,
                                   states={'draft': [('readonly', False)]},
                                   help="Pricelist for current reservation.")
    partner_invoice_id = fields.Many2one('res.partner', 'Invoice Address',
                                         readonly=True,
                                         states={'draft':
                                                     [('readonly', False)]},
                                         help="Invoice address for "
                                              "current reservation.")
    partner_order_id = fields.Many2one('res.partner', 'Ordering Contact',
                                       readonly=True,
                                       states={'draft':
                                                   [('readonly', False)]},
                                       help="The name and address of the "
                                            "contact that requested the order "
                                            "or quotation.")
    partner_shipping_id = fields.Many2one('res.partner', 'Delivery Address',
                                          readonly=True,
                                          states={'draft':
                                                      [('readonly', False)]},
                                          help="Delivery address"
                                               "for current reservation. ")

    folio_id = fields.Many2many('hotel.folio', 'hotel_folio_reservation_rel',
                                'order_id', 'invoice_id', string='Folio')
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

@api.onchange('partner_id')
def onchange_partner_id(self):
    '''
    When you change partner_id it will update the partner_invoice_id,
    partner_shipping_id and pricelist_id of the hotel reservation as well
    ---------------------------------------------------------------------
    @param self: object pointer
    '''
    if not self.partner_id:
        self.partner_invoice_id = False
        self.partner_shipping_id = False
        self.partner_order_id = False
    else:
        addr = self.partner_id.address_get(['delivery', 'invoice',
                                            'contact'])
        self.partner_invoice_id = addr['invoice']
        self.partner_order_id = addr['contact']
        self.partner_shipping_id = addr['delivery']
        self.pricelist_id = self.partner_id.property_product_pricelist.id


    @api.multi
    def create_folio(self):
        """
        This method is for create new hotel folio.
        -----------------------------------------
        @param self: The object pointer
        @return: new record set for hotel folio.
        """
        hotel_folio_obj = self.env['hotel.folio']
        room_obj = self.env['hotel.room']
        for reservation in self:
            folio_lines = []
            checkin_date = reservation['checkin']
            checkout_date = reservation['checkout']
            if not self.checkin < self.checkout:
                raise ValidationError(_('Checkout date should be greater \
                                         than the Check-in date.'))
            duration_vals = (self.onchange_check_dates
                             (checkin_date=checkin_date,
                              checkout_date=checkout_date, duration=False))
            duration = duration_vals.get('duration') or 0.0
            folio_vals = {
                'date_order': reservation.date_order,
                'warehouse_id': reservation.warehouse_id.id,
                'partner_id': reservation.partner_id.id,
                'pricelist_id': reservation.pricelist_id.id,
                'partner_invoice_id': reservation.partner_invoice_id.id,
                'partner_shipping_id': reservation.partner_shipping_id.id,
                'checkin_date': reservation.checkin,
                'checkout_date': reservation.checkout,
                'duration': duration,
                'reservation_id': reservation.id,
                'service_lines': reservation['folio_id']
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

