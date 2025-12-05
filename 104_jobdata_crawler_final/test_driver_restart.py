import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the directory containing the crawler to sys.path
sys.path.append(r"e:\Antigravity_HOME_PC\WLS\104_jobdata_crawler_final")

# Mock undetected_chromedriver before importing the crawler
sys.modules["undetected_chromedriver"] = MagicMock()

# Import the module under test
# We need to use importlib to import it because the filename starts with a number
import importlib.util
spec = importlib.util.spec_from_file_location("crawler", r"e:\Antigravity_HOME_PC\WLS\104_jobdata_crawler_final\104_crawler_final.py")
crawler = importlib.util.module_from_spec(spec)
sys.modules["crawler"] = crawler
spec.loader.exec_module(crawler)

class TestRestartDriver(unittest.TestCase):
    @patch("crawler.uc.Chrome")
    def test_restart_driver_success(self, mock_chrome):
        # Setup mock to return a driver object
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver
        
        args = MagicMock()
        args.headless = False
        
        # Run
        driver = crawler.restart_driver(None, args)
        
        # Verify
        self.assertIsNotNone(driver)
        self.assertEqual(driver, mock_driver)
        self.assertEqual(mock_chrome.call_count, 1)

    @patch("crawler.uc.Chrome")
    def test_restart_driver_failure_retry(self, mock_chrome):
        # Setup mock to raise exception
        mock_chrome.side_effect = Exception("Connection refused")
        
        args = MagicMock()
        args.headless = False
        
        # Run
        driver = crawler.restart_driver(None, args)
        
        # Verify
        self.assertIsNone(driver)
        self.assertEqual(mock_chrome.call_count, 3) # Should retry 3 times

    @patch("crawler.uc.Chrome")
    def test_restart_driver_success_after_retry(self, mock_chrome):
        # Setup mock to fail twice then succeed
        mock_driver = MagicMock()
        mock_chrome.side_effect = [Exception("Fail 1"), Exception("Fail 2"), mock_driver]
        
        args = MagicMock()
        args.headless = False
        
        # Run
        driver = crawler.restart_driver(None, args)
        
        # Verify
        self.assertIsNotNone(driver)
        self.assertEqual(driver, mock_driver)
        self.assertEqual(mock_chrome.call_count, 3)

if __name__ == "__main__":
    unittest.main()
