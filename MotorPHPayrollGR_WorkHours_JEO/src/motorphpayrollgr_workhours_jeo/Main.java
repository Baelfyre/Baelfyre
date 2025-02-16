package motorphpayrollgr_workhours_jeo;

import java.time.LocalDate;
import java.time.LocalTime;

public class Main {
    public static void main(String[] args) {
        Employee[] employees = new Employee[10034];

        for (int i = 0; i < 10034; i++) {
            employees[i] = new Employee(
                    i + 1,
                    "Last Name " + i,
                    "First Name " + i,
                    LocalDate.of(2024, 6, 3),
                    LocalTime.of(8, 59),
                    LocalTime.of(18, 59)
            );
        }

        for (int i = 0; i < 10034; i++) {
            System.out.println("Employee " + (i + 1) + ": " + employees[i].getWorkHoursDetails());
        }
    }
}
