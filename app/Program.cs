using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

// The exam program. It gets the path of an input file, and prints the report.
// Run it from the exam folder:  python check/run_checks.py run
// Without a path, it reads data/sample.txt.
class Program
{
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
    }

    static int ReadReportDay(string[] lines)
    {
        return int.Parse(lines[0].Split(':')[1].Trim());
    }

    // The lines after the two first ones, each split into its fields
    static List<string[]> ReadRows(string[] lines)
    {
        List<string[]> rows = new List<string[]>();
        for (int i = 2; i < lines.Length; i++)
        {
            if (lines[i].Trim() == "") continue;
            string[] fields = lines[i].Split(',');
            for (int j = 0; j < fields.Length; j++) fields[j] = fields[j].Trim();
            rows.Add(fields);
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
