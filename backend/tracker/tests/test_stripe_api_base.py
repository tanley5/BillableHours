"""STRIPE_API_BASE wiring for interchangeable Stripe sim / live."""
from django.test import SimpleTestCase, override_settings


class StripeApiBaseTests(SimpleTestCase):
    @override_settings(STRIPE_SECRET_KEY="sk_test_sim", STRIPE_API_BASE="http://stripe-sim:12111")
    def test_escrow_stripe_helper_sets_api_base(self):
        from tracker import stripe_escrow

        s = stripe_escrow._stripe()
        self.assertEqual(s.api_key, "sk_test_sim")
        self.assertEqual(s.api_base, "http://stripe-sim:12111")

    @override_settings(STRIPE_SECRET_KEY="sk_test_sim", STRIPE_API_BASE="http://stripe-sim:12111")
    def test_connect_stripe_helper_sets_api_base(self):
        from tracker import stripe_connect

        s = stripe_connect._stripe()
        self.assertEqual(s.api_key, "sk_test_sim")
        self.assertEqual(s.api_base, "http://stripe-sim:12111")

    @override_settings(STRIPE_SECRET_KEY="sk_live", STRIPE_API_BASE="")
    def test_empty_api_base_leaves_default(self):
        import stripe
        from tracker import stripe_escrow

        before = stripe.DEFAULT_API_BASE
        stripe.api_base = before
        s = stripe_escrow._stripe()
        self.assertEqual(s.api_key, "sk_live")
        self.assertEqual(s.api_base, before)
