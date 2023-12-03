import unittest

from app.pkg.googauth.googauth import *


class GoogAuthTests(unittest.TestCase):

    def test_generate_secret_key(self):
        # Test valid length
        secret_key = generate_secret_key(16)
        self.assertEqual(len(secret_key), 16)

        # Test invalid length
        with self.assertRaises(TypeError):
            generate_secret_key(4)

    def test_validate_secret(self):
        # Test valid secret
        valid_secret = 'JBSWY3DPEHPK3PXP'
        self.assertTrue(validate_secret(valid_secret))

        # Test invalid secret
        invalid_secret = '1234567890'
        self.assertFalse(validate_secret(invalid_secret))

    def test_generate_code(self):
        # Test with current time
        secret = 'JBSWY3DPEHPK3PXP'
        code = generate_code(secret)
        self.assertIsInstance(code, bytes)

        # Test with custom value
        value = 123456
        code = generate_code(secret, value)
        self.assertIsInstance(code, bytes)

    def test_verify_counter_based(self):
        # Test valid code
        secret = 'JBSWY3DPEHPK3PXP'
        code = '123456'
        counter = 0
        window = 3
        result = verify_counter_based(secret, code, counter, window)
        self.assertEqual(result, counter)

        # Test invalid code
        code = '654321'
        result = verify_counter_based(secret, code, counter, window)
        self.assertIsNone(result)

    def test_verify_time_based(self):
        # Test valid code
        secret = 'JBSWY3DPEHPK3PXP'
        code = '123456'
        result = verify_time_based(secret, code)
        self.assertIsInstance(result, int)

        # Test invalid code
        code = '654321'
        result = verify_time_based(secret, code)
        self.assertIsNone(result)

    def test_get_otpauth_url(self):
        user = 'testuser'
        domain = 'example.com'
        secret = 'JBSWY3DPEHPK3PXP'
        otpauth_url = get_otpauth_url(user, domain, secret)
        expected_url = 'otpauth://totp/testuser@example.com?secret=JBSWY3DPEHPK3PXP'
        self.assertEqual(otpauth_url, expected_url)

    def test_get_barcode_url(self):
        user = 'testuser'
        domain = 'example.com'
        secret = 'JBSWY3DPEHPK3PXP'
        barcode_url = get_barcode_url(user, domain, secret)
        expected_url = 'https://www.google.com/chart?chs=200x200&chld=M|0&cht=qr&chl=otpauth%3A%2F%2Ftotp%2Ftestuser%40example.com%3Fsecret%3DJBSWY3DPEHPK3PXP'
        self.assertEqual(barcode_url, expected_url)


if __name__ == '__main__':
    unittest.main()
