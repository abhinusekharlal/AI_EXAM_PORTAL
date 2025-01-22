from django.test import TestCase, Client
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils import timezone
from .models import User
from datetime import timedelta

class UserRegistrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('Users:register')
        self.verify_email_url = reverse('Users:verify-email', args=[get_random_string(64)])
        self.user_data = {
            'username': 'testuser',
            'email': 'swathisuresh145@gmail.com',
            'password1': 'testpassword123',
            'password2': 'testpassword123',
            'user_type': 'student',
        }

    def test_user_registration(self):
        response = self.client.post(self.register_url, self.user_data)
        self.assertEqual(response.status_code, 302)  # Redirect to login page
        user = User.objects.get(username='testuser')
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_email_verified)
        self.assertIsNotNone(user.email_verification_token)

    def test_email_verification(self):
        user = User.objects.create_user(
            username='testuser',
            email='swathisuresh145@gmail.com',
            password='testpassword123',
            user_type='student',
            is_active=False,
            email_verification_token=get_random_string(64),
            email_token_created_at=timezone.now()
        )
        verify_url = reverse('Users:verify-email', args=[user.email_verification_token])
        response = self.client.get(verify_url)
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_email_verified)
        self.assertEqual(user.email_verification_token, '')

    def test_expired_verification_link(self):
        user = User.objects.create_user(
            username='testuser',
            email='swathisuresh145@gmail.com',
            password='testpassword123',
            user_type='student',
            is_active=False,
            email_verification_token=get_random_string(64),
            email_token_created_at=timezone.now() - timedelta(hours=25)
        )
        verify_url = reverse('Users:verify-email', args=[user.email_verification_token])
        response = self.client.get(verify_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Verification link expired')
        with self.assertRaises(User.DoesNotExist):
            User.objects.get(username='testuser')
