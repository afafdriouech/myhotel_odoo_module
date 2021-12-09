from odoo import models, fields, api, exceptions, _
from dateutil.relativedelta import relativedelta
from  odoo.exceptions import ValidationError,UserError
import pytz
import time
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as dt
from datetime import datetime, timedelta


class reservation(models.Model):
    _name = 'myhotel.reservation'
    _rec_name = "reservation_no"
    _order = 'reservation_no desc'

    reservation_no = fields.Char('Reservation No', readonly=True)
    date_order = fields.Datetime('Date reservation', readonly=True, required=True, index=True, default=(lambda *a: time.strftime(dt)))
    checkin = fields.Datetime('Date d\'arrivée prévue', required=True, readonly=True,
                              states={'draft': [('readonly', False)]})
    checkout = fields.Datetime('Date départ prévue', required=True, readonly=True,
                              states={'draft': [('readonly', False)]})
    adults = fields.Integer('Adultes', help='List of adults there in guest list.', readonly=True,
                              states={'draft': [('readonly', False)]})
    children = fields.Integer('Enfants', help='Number of children there in guest list.', readonly=True,
                              states={'draft': [('readonly', False)]})
    client_id = fields.Many2one('res.partner', ondelete='cascade', string="Client", index=True, required=True, readonly=True,
                              states={'draft': [('readonly', False)]})
    reservation_line = fields.One2many('hotel_reservation.line', 'line_id', 'Reservation Line', help='Details de reservation d\'une chambre'
                                       , readonly=True, states={'draft': [('readonly', False)]},)

    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm'),('cancel', 'Cancel'), ('done', 'Done')],
                             'State', readonly=True, default=lambda *a: 'draft')

    client_order_id = fields.Many2one('res.partner', 'Ordering Contact', readonly=True,
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
    def onchange_client_id(self):
        '''
        When you change partner_id it will update the partner_invoice_id,
        partner_shipping_id and pricelist_id of the hotel reservation as well
        ---------------------------------------------------------------------
        @param self: object pointer
        '''
        if not self.client_id:
            self.client_invoice_id = False
            self.client_invoice_id = False
            self.client_order_id = False
        else:
            addr = self.client_id.address_get(['delivery', 'invoice',
                                                'contact'])
            self.client_invoice_id = addr['invoice']
            self.client_order_id = addr['contact']
            #self.pricelist_id = self.partner_id.property_product_pricelist.id


    @api.multi
    def unlink(self):
        """
        @return: True/False.
        """
        for reserv_rec in self:
            if reserv_rec.state != 'draft':
                raise ValidationError(_('impossible de supprimer la reservation dans cet etat: ') % (reserv_rec.state))
        return super(reservation, self).unlink()

    @api.model
    def create(self, vals):

        if not vals:
            vals = {}
        vals['reservation_no'] = self.env['ir.sequence'].next_by_code('myhotel.reservation') or 'New'
        return super(reservation, self).create(vals)

    @api.multi
    def copy(self):
        ctx = dict(self._context) or {}
        ctx.update({'duplicate': True})
        return super(reservation, self.with_context(ctx)).copy()

    @api.constrains('reservation_line', 'adults', 'children')
    def check_reservation_rooms(self):
        '''
        This method is used to validate the reservation_line.
        and checking the room capacity
        '''
        ctx = dict(self._context) or {}
        for reservation in self:
            cap = 0
            for rec in reservation.reservation_line:
                if len(rec.reserve) == 0:
                    raise exceptions.ValidationError('Selectionnez des chambres SVP!')
                for room in rec.reserve:
                    cap += room.capacite
            if not ctx.get('duplicate'):
                if (reservation.adults + reservation.children) > cap:
                    raise exceptions.ValidationError('Capacite du chambre depassee \n'
                        ' Selectionnez des chambres qui conviennent a votre nombre.')
            if reservation.adults <= 0:
                raise exceptions.ValidationError('le nombre d\'adultes doit etre superieur a 0')



    @api.constrains('checkin', 'checkout')
    def check_in_out_dates(self):
        """
        When date_order is less then check-in date or
        Checkout date should be greater than the check-in date.
        """
        if self.checkout and self.checkin:
            if self.checkin < self.date_order:
                raise exceptions.ValidationError('la date d\'arrivée prévue doit depasser la date d\'ajourd\'hui.')
            if self.checkout < self.checkin:
                raise exceptions.ValidationError('la date de départ prévue doit depasser la date d\'arrivée prévue.')

    @api.onchange('checkout', 'checkin')
    def on_change_checkout(self):
        '''
        When you change checkout or checkin update dummy field
        -----------------------------------------------------------
        @param self: object pointer
        @return: raise warning depending on the validation
        '''
        checkout_date = time.strftime(dt)
        checkin_date = time.strftime(dt)
        if not (checkout_date and checkin_date):
            return {'value': {}}
        delta = timedelta(days=1)
        dat_a = time.strptime(checkout_date, dt)[:5]
        addDays = datetime(*dat_a) + delta
        self.dummy = addDays.strftime(dt)

    #staaaaates
    @api.multi
    def check_overlap(self, date1, date2):
        date2 = datetime.strptime(date2, '%Y-%m-%d')
        date1 = datetime.strptime(date1, '%Y-%m-%d')
        delta = date2 - date1
        return set([date1 + timedelta(days=i) for i in range(delta.days + 1)])

    @api.multi
    def confirmed_reservation(self):
        """
        This method create a new record set for hotel room reservation line
        -------------------------------------------------------------------
        @param self: The object pointer
        @return: new record set for hotel room reservation line.
        """
        reservation_line_obj = self.env['hotel.room.reservation.line']
        vals = {}
        for reservation in self:
            reserv_checkin = datetime.strptime(reservation.checkin, dt)
            reserv_checkout = datetime.strptime(reservation.checkout, dt)
            room_bool = False
            for line_id in reservation.reservation_line:
                for room_id in line_id.reserve:
                    if room_id.room_reservation_line_ids:
                        for reserv in room_id.room_reservation_line_ids. \
                                search([('status', 'in', ('confirm', 'done')),
                                        ('room_id', '=', room_id.id)]):
                            check_in = datetime.strptime(reserv.check_in, dt)
                            check_out = datetime.strptime(reserv.check_out, dt)
                            if check_in <= reserv_checkin <= check_out:
                                room_bool = True
                            if check_in <= reserv_checkout <= check_out:
                                room_bool = True
                            if reserv_checkin <= check_in and \
                                    reserv_checkout >= check_out:
                                room_bool = True
                            mytime = "%Y-%m-%d"
                            r_checkin = datetime.strptime(reservation.checkin,
                                                          dt).date()
                            r_checkin = r_checkin.strftime(mytime)
                            r_checkout = datetime. \
                                strptime(reservation.checkout, dt).date()
                            r_checkout = r_checkout.strftime(mytime)
                            check_intm = datetime.strptime(reserv.check_in,
                                                           dt).date()
                            check_outtm = datetime.strptime(reserv.check_out,
                                                            dt).date()
                            check_intm = check_intm.strftime(mytime)
                            check_outtm = check_outtm.strftime(mytime)
                            range1 = [r_checkin, r_checkout]
                            range2 = [check_intm, check_outtm]
                            overlap_dates = self.check_overlap(*range1) \
                                            & self.check_overlap(*range2)
                            overlap_dates = [datetime.strftime(dates,
                                                               '%d/%m/%Y') for
                                             dates in overlap_dates]
                            if room_bool:
                                raise exceptions.ValidationError(_('Vous avez essayer de confirmer '
                                                        'une reservation avec une chambre'
                                                        ' qui est '
                                                        'occupee '
                                                        'dans cette periode '
                                                        'les dates de chevauchement sont '
                                                        '%s') % overlap_dates)
                            else:
                                self.state = 'confirm'
                                vals = {'room_id': room_id.id,
                                        'check_in': reservation.checkin,
                                        'check_out': reservation.checkout,
                                        'state': 'assigned',
                                        'reservation_id': reservation.id,
                                        }
                                room_id.write({'isroom': False,
                                               'status': 'occupied'})
                        else:
                            self.state = 'confirm'
                            vals = {'room_id': room_id.id,
                                    'check_in': reservation.checkin,
                                    'check_out': reservation.checkout,
                                    'state': 'assigned',
                                    'reservation_id': reservation.id,
                                    }
                            room_id.write({'isroom': False,
                                           'status': 'occupied'})
                    else:
                        self.state = 'confirm'
                        vals = {'room_id': room_id.id,
                                'check_in': reservation.checkin,
                                'check_out': reservation.checkout,
                                'state': 'assigned',
                                'reservation_id': reservation.id,
                                }
                        room_id.write({'isroom': False,
                                       'status': 'occupied'})
                    reservation_line_obj.create(vals)
        return True

    @api.multi
    def cancel_reservation(self):
        """
        This method cancel record set for hotel room reservation line
        ------------------------------------------------------------------
        @param self: The object pointer
        @return: cancel record set for hotel room reservation line.
        """
        room_res_line_obj = self.env['hotel.room.reservation.line']
        hotel_res_line_obj = self.env['hotel_reservation.line']
        self.state = 'cancel'
        room_reservation_line = room_res_line_obj.search([('reservation_id',
                                                           'in', self.ids)])
        room_reservation_line.write({'state': 'unassigned'})
        room_reservation_line.unlink()
        reservation_lines = hotel_res_line_obj.search([('line_id',
                                                        'in', self.ids)])
        for reservation_line in reservation_lines:
            reservation_line.reserve.write({'isroom': True,
                                            'status': 'available'})
        return True

    @api.multi
    def set_to_draft_reservation(self):
        self.state = 'draft'
        return True

    @api.multi
    def send_reservation_mail(self):
        '''
        This function opens the email window
        @param self: object pointer
        '''
        assert len(self._ids) == 1, 'This is for a single id at a time.'
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = (ir_model_data.get_object_reference
            ('myhotel_reservation',
             'mail_template_reservation')[1])
        except ValueError:
            template_id = False
        try:
            compose_form_id = (ir_model_data.get_object_reference
            ('mail',
             'email_compose_message_wizard_form')[1])
        except ValueError:
            compose_form_id = False
        ctx = dict()
        ctx.update({
            'default_model': 'myhotel.reservation',
            'default_res_id': self._ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'force_send': True,
            'mark_so_as_sent': True
        })
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
            'force_send': True
        }

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
                #'client_id': reservation.client_id.id,
                #'client_invoice_id': reservation.client_invoice_id.id,
                'checkin_date': reservation.checkin,
                'checkout_date': reservation.checkout,
                'duration': duration,
                'reservation_id': reservation.id,
                # 'service_lines': reservation['folio_id']
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



    @api.multi
    def onchange_check_dates(self, checkin_date=False, checkout_date=False, duration=False):
        '''
        This method gives the duration between check in checkout if
        customer will leave only for some hour it would be considers
        as a whole day. If customer will checkin checkout for more or equal
        hours, which configured in company as additional hours than it would
        be consider as full days
        --------------------------------------------------------------------
        @param self: object pointer
        @return: Duration and checkout_date
        '''
        value = {}
        configured_addition_hours = 5
        duration = 0
        if checkin_date and checkout_date:
            chkin_dt = datetime.strptime(checkin_date, dt)
            chkout_dt = datetime.strptime(checkout_date, dt)
            dur = chkout_dt - chkin_dt
            duration = dur.days + 1
            if configured_addition_hours > 0:
                additional_hours = abs((dur.seconds / 60))
                if additional_hours <= abs(configured_addition_hours * 60):
                    duration -= 1
        value.update({'duration': duration})
        return value

########################################################################

class HotelRoomReservationLine(models.Model):
        _name = 'hotel.room.reservation.line'
        _description = 'Hotel Room Reservation'
        _rec_name = 'room_id'

        room_id = fields.Many2one('myhotel.chambre', string='Chambre id')
        check_in = fields.Datetime('Check In Date', required=True)
        check_out = fields.Datetime('Check Out Date', required=True)
        state = fields.Selection([('assigned', 'Assigned'), ('unassigned', 'Unassigned')], 'Room Status')
        reservation_id = fields.Many2one('myhotel.reservation', string='Reservation')
        status = fields.Selection(string='state', related='reservation_id.state')


#######################################################################

class HotelReservationLine(models.Model):

    _name = "hotel_reservation.line"
    _description = "Reservation Line"

    name = fields.Char('Name')
    line_id = fields.Many2one('myhotel.reservation')
    reserve = fields.Many2many('myhotel.chambre', 'hotel_reservation_line_id', 'room_id', required=True,
                               domain="[('isroom','=',True),\
                                                             ('categorie_id','=',categ_id)]")

    categ_id = fields.Many2one('myhotel.categorie', 'Room Type')


    @api.onchange('categ_id')
    def on_change_categ(self):
        '''
        When you change categ_id it check checkin and checkout are
        filled or not if not then raise warning
        -----------------------------------------------------------
        @param self: object pointer
        '''
        hotel_room_obj = self.env['myhotel.chambre']
        hotel_room_ids = hotel_room_obj.search([('categorie_id', '=', self.categ_id.id)])
        room_ids = []
        if not self.line_id.checkin:
            raise exceptions.ValidationError('Avant de choisir une chambre,\n vous devez \
                                     choisir la date d\'arrivee  ou la date de depart.')
        for room in hotel_room_ids:
            assigned = False
            for line in room.room_reservation_line_ids:
                if line.status != 'cancel':
                    if(self.line_id.checkin <= line.check_in <=
                        self.line_id.checkout) or (self.line_id.checkin <=
                                                   line.check_out <=
                                                   self.line_id.checkout):
                        assigned = True
                    elif(line.check_in <= self.line_id.checkin <=
                         line.check_out) or (line.check_in <=
                                             self.line_id.checkout <=
                                             line.check_out):
                        assigned = True
            if not assigned:
                room_ids.append(room.id)
        domain = {'reserve': [('id', 'in', room_ids)]}
        return {'domain': domain}


    @api.multi
    def unlink(self):
        """
        @return: True/False.
        """
        hotel_room_reserv_line_obj = self.env['hotel.room.reservation.line']
        for reserv_rec in self:
            for rec in reserv_rec.reserve:
                hres_arg = [('room_id', '=', rec.id),
                            ('reservation_id', '=', reserv_rec.line_id.id)]
                myobj = hotel_room_reserv_line_obj.search(hres_arg)
                if myobj.ids:
                    rec.write({'isroom': True, 'status': 'available'})
                    myobj.unlink()
        return super(HotelReservationLine, self).unlink()

#############################################

class planning(models.Model):

    _name = 'myhotel.planning'
    _description = 'Planning des reservations'

    name = fields.Char('Planning des reservations', default='Planning des reservations', invisible=True)
    date_from = fields.Datetime('Date de')
    date_to = fields.Datetime('Date a')
    summary_header = fields.Text('En-tete planning')
    room_summary = fields.Text('Planning des reservations')

    @api.model
    def default_get(self, fields):
        """
        set date-from to today's date and date-to to today's date + 30
        """
        if self._context is None:
            self._context = {}
        res = super(planning, self).default_get(fields)
        # Added default datetime as today and date to as today + 30.
        from_dt = datetime.today()
        dt_from = from_dt.strftime(dt)
        to_dt = from_dt + relativedelta(days=30)
        dt_to = to_dt.strftime(dt)
        res.update({'date_from': dt_from, 'date_to': dt_to})

        if not self.date_from and self.date_to:
            date_today = datetime.datetime.today()
            first_day = datetime.datetime(date_today.year,
                                          date_today.month, 1, 0, 0, 0)

            first_temp_day = first_day + relativedelta(months=1)
            last_temp_day = first_temp_day - relativedelta(days=1)
            last_day = datetime.datetime(last_temp_day.year,
                                         last_temp_day.month,
                                         last_temp_day.day, 23, 59, 59)
            date_froms = first_day.strftime(dt)
            date_ends = last_day.strftime(dt)
            res.update({'date_from': date_froms, 'date_to': date_ends})
        return res


    @api.multi
    def room_reservation(self):

        mod_obj = self.env['ir.model.data']
        if self._context is None:
            self._context = {}
        model_data_ids = mod_obj.search([('model', '=', 'ir.ui.view'),
                                         ('name', '=', 'view_hotel_reservation_form')])
        resource_id = model_data_ids.read(fields=['res_id'])[0]['res_id']
        return {'name': _('Reconcile Write-Off'),
                'context': self._context,
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'myhotel.reservation',
                'views': [(resource_id, 'form')],
                'type': 'ir.actions.act_window',
                'target': 'new',
                }

    @api.onchange('date_from', 'date_to')
    def get_room_summary(self):
        res = {}
        all_detail = []
        room_obj = self.env['myhotel.chambre']
        reservation_line_obj = self.env['hotel.room.reservation.line']
        date_range_list = []
        main_header = []
        summary_header_list = ['Chambres']
        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                raise UserError(_('Corrigez les dates!'))
            if self._context.get('tz', False):
                timezone = pytz.timezone(self._context.get('tz', False))
            else:
                timezone = pytz.timezone('UTC')
            d_frm_obj = datetime.strptime(self.date_from, dt)\
                .replace(tzinfo=pytz.timezone('UTC')).astimezone(timezone)
            d_to_obj = datetime.strptime(self.date_to, dt)\
                .replace(tzinfo=pytz.timezone('UTC')).astimezone(timezone)
            temp_date = d_frm_obj
            while(temp_date <= d_to_obj):

                val = ''
                val = (str(temp_date.strftime("%a")) + ' ' +
                       str(temp_date.strftime("%b")) + ' ' +
                       str(temp_date.strftime("%d")))
                summary_header_list.append(val)
                date_range_list.append(temp_date.strftime(dt))
                temp_date = temp_date + timedelta(days=1)
            all_detail.append(summary_header_list)
            room_ids = room_obj.search([])
            all_room_detail = []
            for room in room_ids:
                room_detail = {}
                room_list_stats = []
                room_detail.update({'name': room.name or ''})
                if not room.room_reservation_line_ids:
                    for chk_date in date_range_list:
                        room_list_stats.append({'state': 'Free',
                                                'date': chk_date,
                                                'room_id': room.id})
                else:
                    for chk_date in date_range_list:
                        ch_dt = chk_date[:10] + ' 23:59:59'
                        ttime = datetime.strptime(ch_dt, dt)
                        c = ttime.replace(tzinfo=timezone). \
                            astimezone(pytz.timezone('UTC'))
                        chk_date = c.strftime(dt)
                        reserline_ids = room.room_reservation_line_ids.ids
                        reservline_ids = (reservation_line_obj.search
                                          ([('id', 'in', reserline_ids),
                                            ('check_in', '<=', chk_date),
                                            ('check_out', '>=', chk_date),
                                            ('state', '=', 'assigned')
                                            ]))
                        if not reservline_ids:
                            sdt = dt
                            chk_date = datetime.strptime(chk_date, sdt)
                            chk_date = datetime.strftime(chk_date - timedelta(days=1), sdt)
                            reservline_ids = (reservation_line_obj.search
                                              ([('id', 'in', reserline_ids),
                                                ('check_in', '<=', chk_date),
                                                ('check_out', '>=', chk_date),
                                                ('state', '=', 'assigned')]))

                            for res_room in reservline_ids:
                                rrci = res_room.check_in
                                rrco = res_room.check_out
                                cid = datetime.strptime(rrci, dt)
                                cod = datetime.strptime(rrco, dt)
                                dur = cod - cid
                                if room_list_stats:
                                    count = 0
                                    for rlist in room_list_stats:
                                        cidst = datetime.strftime(cid, dt)
                                        codst = datetime.strftime(cod, dt)
                                        rm_id = res_room.room_id.id
                                        ci = rlist.get('date') >= cidst
                                        co = rlist.get('date') <= codst
                                        rm = rlist.get('room_id') == rm_id
                                        st = rlist.get('state') == 'Reserved'
                                        if ci and co and rm and st:
                                            count += 1
                                    if count - dur.days == 0:
                                        con_add = 5
                                        amin = 0.0
                                        # When configured_addition_hours is
                                        # greater than zero then we calculate
                                        # additional minutes
                                        if con_add > 0:
                                            amin = abs(con_add * 60)
                                        hr_dur = abs((dur.seconds / 60))
                                        # When additional minutes is greater
                                        # than zero then check duration with
                                        # extra minutes and give the room
                                        # reservation status is reserved or
                                        # free
                                        if amin > 0:
                                            if hr_dur >= amin:
                                                reservline_ids = True
                                            else:
                                                reservline_ids = False
                                        else:
                                            if hr_dur > 0:
                                                reservline_ids = True
                                            else:
                                                reservline_ids = False
                                    else:
                                        reservline_ids = False
                                        chk_state = ['draft', 'cancel']
                                        if reservline_ids:
                                            room_list_stats.append({'state': 'Reserved',
                                                                    'date': chk_date,
                                                                    'room_id': room.id,
                                                                    'is_draft': 'No',
                                                                    'data_model': '',
                                                                    'data_id': 0})
                                        else:
                                            room_list_stats.append({'state': 'Free',
                                                                    'date': chk_date,
                                                                    'room_id': room.id})

                                    room_detail.update({'value': room_list_stats})
                                    all_room_detail.append(room_detail)
                                main_header.append({'header': summary_header_list})
                                self.summary_header = str(main_header)
                                self.room_summary = str(all_room_detail)
                        return res

##############################
class QuickRoomReservation(models.TransientModel):
    _name = 'quick.room.reservation'
    _description = 'Quick Room Reservation'

    client_id = fields.Many2one('res.partner', string="Client", required=True)
    check_in = fields.Datetime('Date d\'arrivée prévue', required=True)
    check_out = fields.Datetime('Date départ prévue', required=True)
    room_id = fields.Many2one('myhotel.chambre', 'Chambre', required=True)
    adults = fields.Integer('Adultes', size=64)

    @api.onchange('check_out', 'check_in')
    def on_change_check_out(self):

        if self.check_out and self.check_in:
            if self.check_out < self.check_in:
                raise ValidationError(_('la date de départ prévue doit depasser la date d\'arrivée prévue.'))

    @api.model
    def default_get(self, fields):
        """
        To get default values for the object.
        @param self: The object pointer.
        @param fields: List of fields for which we want default values
        @return: A dictionary which of fields with values.
        """
        if self._context is None:
            self._context = {}
        res = super(QuickRoomReservation, self).default_get(fields)
        if self._context:
            keys = self._context.keys()
            if 'date' in keys:
                res.update({'check_in': self._context['date']})
            if 'room_id' in keys:
                roomid = self._context['room_id']
                res.update({'room_id': int(roomid)})
        return res

    @api.multi
    def room_reserve(self):
        """
        This method create a new record for hotel.reservation
        -----------------------------------------------------
        @param self: The object pointer
        @return: new record set for hotel reservation.
        """
        hotel_res_obj = self.env['myhotel.reservation']
        for res in self:
            rec = (hotel_res_obj.create
                   ({'client_id': res.client_id.id,
                     'checkin': res.check_in,
                     'checkout': res.check_out,
                     'adults': res.adults,
                     'reservation_line': [(0, 0,
                                           {'reserve': [(6, 0,[res.room_id.id])],
                                            'name': (res.room_id and res.room_id.name or '')
                                            })]
                     }))
        return rec