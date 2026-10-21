"""CSV logging of transmitted and received packets."""
import csv
import os


class CSVLogger:
    """
    A class to handle CSV logging operations.

    Attributes:
        file_path (str): The path to the CSV file.
        column_headers (list): The column headers for the CSV file.
        log_execution_time (bool): Whether to log execution time.
    """

    def __init__(self, file_path, column_headers, bool_log_execution_time=False):
        """
        Initialize the CSVLogger.

        Args:
            file_path (str): The path to the CSV file.
            column_headers (list): The column headers for the CSV file.
            bool_log_execution_time (bool, optional): Whether to log execution time. Defaults to False.
        """
        self.file_path = file_path
        self.column_headers = column_headers
        self.log_execution_time = bool_log_execution_time

        # Remove existing file if it exists
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

        # Create CSV file with headers
        self.create_csv(column_headers)

    def create_csv(self, column_headers):
        """
        Create a new CSV file with the specified column headers.

        Args:
            column_headers (list): The column headers for the CSV file.
        """
        with open(self.file_path, mode="w", newline="") as file:
            csv_writer = csv.writer(file)
            csv_writer.writerow(column_headers)
            print("Log file created:", self.file_path)

    def log(self, data, additional_data=None):
        """
        Log data to the CSV file.

        Args:
            data (list): The data to log.
            additional_data (list, optional): Additional data to log. Defaults to None.
        """
        with open(self.file_path, mode="a", newline="") as file:
            data = list(data)
            if additional_data:
                data = additional_data + data
            csv_writer = csv.writer(file)
            csv_writer.writerow(data)
