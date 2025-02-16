package motorphpayrollgr_workhours_jeo;

import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalTime;

public class Employee {
    private int employeeId;
    private String lastName;
    private String firstName;
    private LocalDate date;
    private LocalTime logIn;
    private LocalTime logOut;

    public Employee(int employeeId, String lastName, String firstName, LocalDate date, LocalTime logIn, LocalTime logOut) {
        this.employeeId = employeeId;
        this.lastName = lastName;
        this.firstName = firstName;
        this.date = date;
        this.logIn = logIn;
        this.logOut = logOut;
    }

    public String getWorkHoursDetails() {
        LocalTime scheduledStart = LocalTime.of(9, 0);
        LocalTime lateThreshold = scheduledStart.plusMinutes(10);
        Duration unpaidTime = Duration.ZERO;

        Duration totalWorked = Duration.between(logIn, logOut);

        if (logIn.isAfter(lateThreshold) && totalWorked.compareTo(Duration.ofMinutes(470)) < 0) { 
            unpaidTime = Duration.between(lateThreshold, logIn);
        }

        Duration netWorked = totalWorked.minus(unpaidTime);

        Duration standardWorkHours = Duration.ofHours(8);
        Duration overtime = Duration.ZERO;

        if (netWorked.compareTo(standardWorkHours) > 0) {
            overtime = netWorked.minus(standardWorkHours);
            netWorked = standardWorkHours;
        }

        return String.format(
                "Worked: %d hours %d minutes | Unpaid: %d hours %d minutes | Overtime: %d hours %d minutes",
                netWorked.toHours(), netWorked.toMinutesPart(),
                unpaidTime.toHours(), unpaidTime.toMinutesPart(),
                overtime.toHours(), overtime.toMinutesPart()
        );
    }
}
