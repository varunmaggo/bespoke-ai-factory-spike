package com.fintech.kyc.legacy.model;

// MIGRATE TO: jakarta.validation.*
import javax.validation.constraints.NotBlank;

public class CustomerApplication {

    @NotBlank
    private String fullName;

    @NotBlank
    private String dateOfBirth;   // PROBLEM: stringly-typed date, no format contract

    @NotBlank
    private String nationality;

    private String residencyCountry;

    public CustomerApplication() {
    }

    public CustomerApplication(String fullName, String dateOfBirth,
                               String nationality, String residencyCountry) {
        this.fullName = fullName;
        this.dateOfBirth = dateOfBirth;
        this.nationality = nationality;
        this.residencyCountry = residencyCountry;
    }

    public String getFullName() { return fullName; }
    public void setFullName(String fullName) { this.fullName = fullName; }
    public String getDateOfBirth() { return dateOfBirth; }
    public void setDateOfBirth(String dateOfBirth) { this.dateOfBirth = dateOfBirth; }
    public String getNationality() { return nationality; }
    public void setNationality(String nationality) { this.nationality = nationality; }
    public String getResidencyCountry() { return residencyCountry; }
    public void setResidencyCountry(String residencyCountry) { this.residencyCountry = residencyCountry; }
}
