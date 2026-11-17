//using App;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

// The exam program. It gets the path of an input file, and prints the report.
// Run it from the exam folder:  python check/run_checks.py run
// Without a path, it reads data/sample.txt.
class Program
{
    static int currentReportDay;
    static List<string> originalRows = new List<string>();

    class ProcessedRow
    {
        public string[] Fields;
        public string OriginalText;
        public decimal Fine;
        public int Days;
        public bool Flagged;
    }

    class ReaderFine
    {
        public string ReaderId;
        public string Name;
        public decimal Fine;
    }

    static void Main(string[] args)
    {
        // Hebrew is printed as UTF-8, also on Windows
        Console.OutputEncoding = new UTF8Encoding(false);
        string path = args.Length > 0 ? args[0] : FindSample();
        string[] lines = File.ReadAllLines(path, Encoding.UTF8);
        int reportDay = ReadReportDay(lines);
        List<string[]> rows = ReadRows(lines);
        Console.Error.WriteLine("skeleton ok: read " + Path.GetFileName(path) + " - report day " + reportDay + " - " + rows.Count + " rows");

        // Write your code here. 'reportDay' and 'rows' are ready.
        Console.WriteLine("FINES");
        Console.WriteLine(PrintFinse(rows));
        Console.WriteLine("...");

        Console.WriteLine("FLAGGED");
        Console.WriteLine(PrintFlagged(rows));
        Console.WriteLine("...");

        Console.WriteLine("ERRORS");
        Console.WriteLine(PrintErrors(rows));
        Console.WriteLine("...");

        Console.WriteLine(PrintTotal(rows));
    }

    static List<ProcessedRow> ProcessRows(List<string[]> rows)
    {
        List<ProcessedRow> processedRows = new List<ProcessedRow>();

        for (int i = 0; i < rows.Count; i++)
        {
            ProcessedRow processedRow;
            if (TryProcessRow(rows[i], i, out processedRow))
                processedRows.Add(processedRow);
        }

        return processedRows;
    }

    static bool TryProcessRow(string[] row, int rowIndex, out ProcessedRow processedRow)
    {
        processedRow = null;
        if (row.Length != 6) return false;
        if (string.IsNullOrWhiteSpace(row[0]) || string.IsNullOrWhiteSpace(row[1]) ||
            string.IsNullOrWhiteSpace(row[2]) || string.IsNullOrWhiteSpace(row[3]) ||
            string.IsNullOrWhiteSpace(row[4])) return false;
        if (row[2] != "student" && row[2] != "teacher" && row[2] != "guest" && row[2] != "alumna") return false;
        if (!int.TryParse(row[4], NumberStyles.Integer, CultureInfo.InvariantCulture, out int loanDay)) return false;

        int endDay = currentReportDay;
        bool returned = !string.IsNullOrWhiteSpace(row[5]);
        if (returned && !int.TryParse(row[5], NumberStyles.Integer, CultureInfo.InvariantCulture, out endDay)) return false;
        if (endDay < loanDay) return false;

        int days = endDay - loanDay;
        decimal fine = 0;
        if (row[2] == "student")
        {
            int lateDays = days - 14;
            if (lateDays >= 2) fine = Math.Min(lateDays, 40);
        }
        else if (row[2] == "guest")
        {
            int lateDays = days - 7;
            if (lateDays > 0) fine = decimal.Ceiling(lateDays * 2.5m);
        }
        else if (row[2] == "alumna")
        {
            int lateDays = days - 10;
            if (lateDays > 0) fine = Math.Min(decimal.Ceiling(lateDays * 1.5m), 25);
        }

        processedRow = new ProcessedRow
        {
            Fields = row,
            OriginalText = originalRows[rowIndex],
            Fine = fine,
            Days = days,
            Flagged = row[2] == "teacher" && !returned && days > 60
        };
        return true;
    }

    static string PrintFinse(List<string[]> rows)
    {
        StringBuilder result = new StringBuilder();
        result.Append("reader_id,name,fine");

        List<ProcessedRow> processedRows = ProcessRows(rows);
        Dictionary<string, ReaderFine> finesByReader = new Dictionary<string, ReaderFine>();
        List<ReaderFine> readerFines = new List<ReaderFine>();

        for (int i = 0; i < processedRows.Count; i++)
        {
            string readerId = processedRows[i].Fields[0];
            ReaderFine readerFine;
            if (!finesByReader.TryGetValue(readerId, out readerFine))
            {
                readerFine = new ReaderFine
                {
                    ReaderId = readerId,
                    Name = processedRows[i].Fields[1],
                    Fine = 0
                };
                finesByReader.Add(readerId, readerFine);
                readerFines.Add(readerFine);
            }

            readerFine.Fine += processedRows[i].Fine;
        }

        for (int i = 0; i < readerFines.Count; i++)
        {
            result.AppendLine();
            result.Append(readerFines[i].ReaderId)
                .Append(',')
                .Append(readerFines[i].Name)
                .Append(',')
                .Append(readerFines[i].Fine.ToString("0.##", CultureInfo.InvariantCulture));
        }

        return result.ToString();
    }

    static string PrintFlagged(List<string[]> rows)
    {
        StringBuilder result = new StringBuilder();
        result.Append("reader_id,name");

        List<ProcessedRow> processedRows = ProcessRows(rows);
        HashSet<string> flaggedReaders = new HashSet<string>();
        for (int i = 0; i < processedRows.Count; i++)
        {
            if (!processedRows[i].Flagged) continue;
            if (!flaggedReaders.Add(processedRows[i].Fields[0])) continue;

            result.AppendLine();
            result.Append(processedRows[i].Fields[0])
                .Append(',')
                .Append(processedRows[i].Fields[1]);
        }

        return result.ToString();
    }

    static string PrintErrors(List<string[]> rows)
    {
        StringBuilder result = new StringBuilder();

        for (int i = 0; i < rows.Count; i++)
        {
            ProcessedRow processedRow;
            if (TryProcessRow(rows[i], i, out processedRow)) continue;

            if (result.Length > 0) result.AppendLine();
            result.Append(originalRows[i]);
        }

        return result.ToString();
    }

    static string PrintTotal(List<string[]> rows)
    {
        decimal total = 0;
        List<ProcessedRow> processedRows = ProcessRows(rows);

        for (int i = 0; i < processedRows.Count; i++)
            total += processedRows[i].Fine;

        return "TOTAL," + total.ToString("0.##", CultureInfo.InvariantCulture);
    }

    static int ReadReportDay(string[] lines)
    {
        currentReportDay = int.Parse(lines[0].Split(':')[1].Trim());
        return currentReportDay;
    }

    // The lines after the two first ones, each split into its fields
    static List<string[]> ReadRows(string[] lines)
    {
        List<string[]> rows = new List<string[]>();
        originalRows.Clear();
        for (int i = 2; i < lines.Length; i++)
        {
            if (lines[i].Trim() == "") continue;
            string[] fields = lines[i].Split(',');
            for (int j = 0; j < fields.Length; j++) fields[j] = fields[j].Trim();
            rows.Add(fields);
            originalRows.Add(lines[i]);
        }
        return rows;
    }

    // Without a path, look for data/sample.txt next to the project, also when started from Visual Studio
    static string FindSample()
    {
        DirectoryInfo dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir != null)
        {
            string candidate = Path.Combine(dir.FullName, "data", "sample.txt");
            if (File.Exists(candidate)) return candidate;
            dir = dir.Parent;
        }
        return Path.Combine("data", "sample.txt");
    }
}
