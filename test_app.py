import unittest
from app import app, init_db, get_db

class AmineJewellersTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        init_db()

    def test_login_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_login_success(self):
        response = self.client.post('/', data=dict(username='admin', password='1234'), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard', response.data)

    def test_login_failure(self):
        response = self.client.post('/', data=dict(username='admin', password='wrongpassword'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('ভুল'.encode('utf-8'), response.data)

    def test_unauthenticated_redirects(self):
        for route in ['/dashboard', '/customers', '/gold-stock', '/loans', '/buy-now', '/calculator', '/invoices']:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 302)

    def test_dashboard_route(self):
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)

    def test_customers_route(self):
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
        response = self.client.get('/customers')
        self.assertEqual(response.status_code, 200)

    def test_add_and_delete_customer(self):
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
        add_res = self.client.post('/customer/add', data=dict(
            name='Test User', mobile='01700000000', address='Dhaka', age=30
        ), follow_redirects=True)
        self.assertEqual(add_res.status_code, 200)

        conn = get_db()
        cust = conn.execute("SELECT id FROM customers WHERE name='Test User'").fetchone()
        conn.close()
        self.assertIsNotNone(cust)

        del_res = self.client.get(f'/customer/delete/{cust["id"]}', follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)

    def test_gold_stock_add_and_delete(self):
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
        add_res = self.client.post('/gold-stock', data=dict(
            item_name='Gold Chain', karat='22K', weight=11.664, quantity=1, purchase_rate=185000
        ), follow_redirects=True)
        self.assertEqual(add_res.status_code, 200)

        conn = get_db()
        stock = conn.execute("SELECT id FROM gold_stock WHERE item_name='Gold Chain'").fetchone()
        conn.close()
        self.assertIsNotNone(stock)

        del_res = self.client.get(f'/gold-stock/delete/{stock["id"]}', follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)

    def test_loans_add_and_voucher(self):
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
        add_res = self.client.post('/loans', data=dict(
            customer_name='Loan Client', mobile='01800000000', item_details='Ring',
            weight=5.5, amount=50000, interest_rate=2.5
        ), follow_redirects=True)
        self.assertEqual(add_res.status_code, 200)

        conn = get_db()
        loan = conn.execute("SELECT id, voucher_id FROM loans WHERE customer_name='Loan Client'").fetchone()
        conn.close()
        self.assertIsNotNone(loan)

        voucher_res = self.client.get(f'/loan-voucher/{loan["voucher_id"]}')
        self.assertEqual(voucher_res.status_code, 200)

        del_res = self.client.get(f'/loans/delete/{loan["id"]}', follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)

    def test_buy_now_add_and_delete(self):
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
        add_res = self.client.post('/buy-now', data=dict(
            customer_name='Buyer', mobile='01900000000', item_details='Bangle', grade='22K Gold',
            bhori_weight=1, ana_weight=2, estimated_price=190000, advance_paid=50000,
            delivery_date='2025-12-31', special_requests='Custom Engraving'
        ), follow_redirects=True)
        self.assertEqual(add_res.status_code, 200)

        conn = get_db()
        order = conn.execute("SELECT id FROM buy_orders WHERE customer_name='Buyer'").fetchone()
        conn.close()
        self.assertIsNotNone(order)

        del_res = self.client.get(f'/buy-now/delete/{order["id"]}', follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)

    def test_calculator_post_and_invoice_create(self):
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
        calc_res = self.client.post('/calculator', data=dict(
            customer_name='Invoice Customer', mobile='01500000000', karat='22K',
            weight=11.664, making=2000, bat=0, stone=500, vat=5
        ))
        self.assertEqual(calc_res.status_code, 200)

        inv_res = self.client.post('/invoice/create', data=dict(
            customer_name='Invoice Customer', mobile='01500000000', karat='22K',
            weight=11.664, rate=185000, gold_value=185000, making=2000,
            bat=0, stone=500, vat=9375, grand_total=196875
        ))
        self.assertEqual(inv_res.status_code, 200)

    def test_invoices_route(self):
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
        response = self.client.get('/invoices')
        self.assertEqual(response.status_code, 200)

    def test_logout_route(self):
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
        response = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
