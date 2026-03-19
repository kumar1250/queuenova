from django.test import TestCase, Client
from django.urls import reverse
from .models import User

class LoginRedirectionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_email = "user@test.com"
        self.admin_email = "admin@test.com"
        self.password = "StrongPass123!@#"
        
        # Create a regular user
        self.user = User.objects.create_user(email=self.user_email, password=self.password)
        
        # Create a staff user (admin)
        self.admin = User.objects.create_user(email=self.admin_email, password=self.password, is_staff=True)

    def test_user_login_redirects_to_org_list(self):
        response = self.client.post(reverse('users:login'), {
            'username': self.user_email,
            'password': self.password
        }, follow=True)
        self.assertRedirects(response, reverse('organizations:organization_list'))

    def test_admin_login_redirects_to_admin_dashboard(self):
        response = self.client.post(reverse('users:login'), {
            'username': self.admin_email,
            'password': self.password
        }, follow=True)
        self.assertRedirects(response, reverse('custom_admin:dashboard'))

    def test_admin_registration_sets_staff_flag(self):
        email = "newadmin@test.com"
        password = "StrongPass123!@#"
        response = self.client.post(reverse('users:admin_register'), {
            'email': email,
            'password1': password,
            'password2': password,
        }, follow=True)
        
        user = User.objects.get(email=email)
        self.assertTrue(user.is_staff)
        self.assertRedirects(response, reverse('custom_admin:dashboard'))
