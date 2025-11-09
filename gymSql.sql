CREATE TABLE Plan (
    planId CHAR(5) PRIMARY KEY,
    planName VARCHAR(100) NOT NULL,
    period INT NOT NULL, -- in months
    monthlyCharge DECIMAL(4, 0) NOT NULL
);

CREATE TABLE SportMember (
    memberId VARCHAR(8) PRIMARY KEY,
    mName VARCHAR(100) NOT NULL,
    birthDate DATE NOT NULL,
    gender CHAR CHECK (gender IN ('M', 'F')),   
    phoneNumber VARCHAR(15) NOT NULL,
    password VARCHAR(255) NOT NULL,
    registerDate DATE NOT NULL,
    status VARCHAR(50) NOT NULL
);

CREATE TABLE Confirm (
    planId CHAR(5),
    memberId VARCHAR(8),
    startDate DATE NOT NULL,
    endDate DATE,
    paymentType VARCHAR(20) NOT NULL,
    dueDate DATE,
    cardType VARCHAR(50),
    cardId VARCHAR(50),
    bankName VARCHAR(100),
    bankId VARCHAR(50),
    Foreign KEY (planId) REFERENCES plan(planId),
    Foreign KEY (memberId) REFERENCES SportMember(memberId)
);

CREATE TABLE Coach (
    coachId CHAR(5) PRIMARY KEY,
    cName VARCHAR(100) NOT NULL,
    coachingType VARCHAR(100) NOT NULL,
    password VARCHAR(20) NOT NULL,
    class VARCHAR(100) 
);

CREATE TABLE Course (
    courseId CHAR(6) PRIMARY KEY,
    courseName VARCHAR(100) NOT NULL,
    classRoom VARCHAR(10),
    studentLimit INT
);

CREATE TABLE CourseSchedule (
    coachId CHAR(5),
    courseId CHAR(6),
    scheduleDate DATE NOT NULL,
    timeSlot VARCHAR(20) NOT NULL,
    PRIMARY KEY (courseId, scheduleDate, timeSlot),
    FOREIGN KEY (courseId) REFERENCES Course(courseId),
    FOREIGN KEY (coachId) REFERENCES Coach(coachId)     
);

CREATE TABLE Booking (
    courseId CHAR(6) NOT NULL,
    scheduleDate DATE NOT NULL,
    timeSlot VARCHAR(20) NOT NULL,
    memberId VARCHAR(8) NOT NULL,
	PRIMARY KEY (courseId, scheduleDate, timeSlot, memberId),
    FOREIGN KEY (courseId, scheduleDate, timeSlot) REFERENCES CourseSchedule(courseId, scheduleDate, timeSlot),
    Foreign KEY (memberId) REFERENCES SportMember(memberId)
);

