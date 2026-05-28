# Gherkin Pattern Examples

Comprehensive examples of Gherkin scenarios for common Django features.

## Authentication & Authorization

### Login/Logout

```gherkin
Feature: User Authentication
  As a registered user
  I want to log in and out securely
  So that I can access my account

  Scenario: Successful login
    Given I am on the login page
    When I enter email "user@example.com"
    And I enter password "SecurePass123"
    And I click the login button
    Then I should be redirected to the dashboard
    And I should see "Welcome back"

  Scenario: Invalid credentials
    Given I am on the login page
    When I enter email "user@example.com"
    And I enter password "WrongPassword"
    And I click the login button
    Then I should see "Invalid credentials"
    And I should remain on the login page

  Scenario: Logout
    Given I am logged in
    When I click logout
    Then I should be logged out
    And I should see the login link
```

### Permission-Based Access

```gherkin
Feature: Content Permissions
  Only authorized users can access protected content

  Scenario: Anonymous user redirected to login
    Given I am not logged in
    When I try to access "/dashboard/"
    Then I should be redirected to "/accounts/login/"
    And I should see "Please log in to continue"

  Scenario: Regular user cannot access admin area
    Given I am logged in as a regular user
    When I try to access "/admin/"
    Then I should see "Permission denied"

  Scenario: Staff user can access admin
    Given I am logged in as staff
    When I visit "/admin/"
    Then I should see the admin interface
```

## CRUD Operations

### Creating Records

```gherkin
Feature: Article Creation
  As an author
  I want to create articles
  So that I can publish content

  Background:
    Given I am logged in as an author
    And there is a category "Technology"

  Scenario: Create article with all fields
    Given I am on the new article page
    When I enter title "My First Post"
    And I enter content "Article content here"
    And I select category "Technology"
    And I enter tags "django, python"
    And I click save
    Then the article should be saved to the database
    And I should see "Article created successfully"

  Scenario: Create without required fields
    Given I am on the new article page
    When I click save without entering data
    Then I should see "Title is required"
    And I should see "Content is required"
    And no article should be created
```

### Updating Records

```gherkin
Feature: Article Editing

  Scenario: Update existing article
    Given I have an article titled "Draft Post"
    And I am viewing the article edit page
    When I change the title to "Published Post"
    And I click update
    Then the article title should be "Published Post" in the database
    And I should see "Article updated successfully"

  Scenario: Cannot edit another user's article
    Given there is an article by another author
    When I try to access the edit page
    Then I should see "Permission denied"
```

### Deleting Records

```gherkin
Feature: Article Deletion

  Scenario: Delete with confirmation
    Given I have an article "Test Article"
    And I am viewing the article page
    When I click delete
    And I confirm the deletion
    Then the article should be deleted from the database
    And I should see "Article deleted successfully"

  Scenario: Cancel deletion
    Given I have an article "Test Article"
    When I click delete
    And I cancel the deletion
    Then the article should still exist
```

## Form Validation

### Single Field Validation

```gherkin
Feature: Email Validation

  Scenario Outline: Invalid email formats
    Given I am on the registration page
    When I enter email "<email>"
    And I submit the form
    Then I should see "<error_message>"

    Examples:
      | email           | error_message           |
      | invalid         | Enter a valid email     |
      | @example.com    | Enter a valid email     |
      | user@           | Enter a valid email     |
      |                 | This field is required  |
```

### Multi-Field Validation

```gherkin
Feature: Password Requirements

  Scenario: Password too short
    Given I am registering
    When I enter password "12345"
    And I submit
    Then I should see "Password must be at least 8 characters"

  Scenario: Passwords don't match
    Given I am registering
    When I enter password "SecurePass123"
    And I enter password confirmation "DifferentPass456"
    And I submit
    Then I should see "Passwords do not match"
```

### Cross-Field Validation

```gherkin
Feature: Date Range Validation

  Scenario: End date before start date
    Given I am creating an event
    When I select start date "2024-01-15"
    And I select end date "2024-01-10"
    And I submit
    Then I should see "End date must be after start date"
```

## Multi-Step Processes

### Wizard/Multi-Page Forms

```gherkin
Feature: Multi-Step Registration

  Scenario: Complete registration wizard
    Given I am on the registration page

    # Step 1
    When I enter email "user@example.com"
    And I enter password "SecurePass123"
    And I click "Next"

    # Step 2
    Then I should see "Step 2 of 3: Profile"
    When I enter first name "John"
    And I enter last name "Doe"
    And I click "Next"

    # Step 3
    Then I should see "Step 3 of 3: Preferences"
    When I check "Email notifications"
    And I select timezone "America/New_York"
    And I click "Complete"

    Then I should see "Registration successful"
    And my account should exist in the database
```

### State Transitions

```gherkin
Feature: Order Workflow

  Background:
    Given I am logged in
    And I have an order in "pending" status

  Scenario: Approve order
    Given I am viewing the order
    When I click "Approve"
    And I confirm approval
    Then the order status should be "approved"
    And the customer should receive a confirmation email

  Scenario: Cannot approve already shipped order
    Given the order status is "shipped"
    When I try to approve the order
    Then I should see "Order already shipped"
```

## Search & Filtering

### Basic Search

```gherkin
Feature: Article Search

  Background:
    Given there are articles:
      | title          | author | status    |
      | Django Basics  | Alice  | published |
      | Python Tips    | Bob    | published |
      | Draft Article  | Alice  | draft     |

  Scenario: Search by title
    Given I am on the articles page
    When I search for "Django"
    Then I should see "Django Basics"
    And I should not see "Python Tips"

  Scenario: No results
    Given I am on the articles page
    When I search for "Nonexistent"
    Then I should see "No articles found"
```

### Multiple Filters

```gherkin
Feature: Product Filtering

  Scenario: Filter by multiple criteria
    Given I am on the products page
    When I filter by category "Electronics"
    And I filter by price range "$100-$500"
    And I sort by "price ascending"
    Then I should see products matching all criteria
    And they should be ordered by price
```

## Pagination

```gherkin
Feature: Article Pagination

  Background:
    Given there are 25 published articles

  Scenario: View first page
    Given I am on the articles page
    Then I should see 10 articles
    And I should see "Page 1 of 3"

  Scenario: Navigate to next page
    Given I am on page 1
    When I click "Next"
    Then I should be on page 2
    And I should see articles 11-20

  Scenario: Jump to specific page
    Given I am on page 1
    When I click page "3"
    Then I should be on page 3
    And I should see articles 21-25
```

## File Upload

```gherkin
Feature: Profile Picture Upload

  Scenario: Upload valid image
    Given I am on my profile page
    When I upload a 2MB JPG image
    Then I should see my new profile picture
    And I should see "Picture updated successfully"

  Scenario: File too large
    Given I am on my profile page
    When I attempt to upload a 15MB image
    Then I should see "File too large. Maximum 10MB"
    And my previous picture should remain

  Scenario: Invalid file type
    Given I am on my profile page
    When I attempt to upload a PDF file
    Then I should see "Invalid file type. Use JPG, PNG, or GIF"
```

## Email Verification

```gherkin
Feature: Email Verification

  Scenario: Verify email with valid token
    Given I have registered with email "user@example.com"
    And I have received a verification email
    When I click the verification link in the email
    Then I should see "Email verified successfully"
    And my account should be marked as verified

  Scenario: Expired verification token
    Given I have a verification link that is 25 hours old
    When I click the expired link
    Then I should see "Verification link expired"
    And I should see "Request new verification email"
```

## Shopping Cart / E-commerce

```gherkin
Feature: Shopping Cart

  Background:
    Given there are products:
      | name         | price | stock |
      | Product A    | 29.99 | 10    |
      | Product B    | 19.99 | 5     |

  Scenario: Add to cart
    Given I am viewing "Product A"
    When I click "Add to Cart"
    Then my cart should contain 1 item
    And the cart total should be "$29.99"

  Scenario: Update quantity
    Given I have "Product A" in my cart
    When I change the quantity to 3
    And I click update
    Then my cart should show 3 items
    And the cart total should be "$89.97"

  Scenario: Remove from cart
    Given I have items in my cart
    When I click remove on "Product A"
    Then "Product A" should not be in my cart
```

## Data Tables in Scenarios

```gherkin
Feature: Bulk User Creation

  Scenario: Create multiple users
    Given I am an admin
    When I import users:
      | email              | role    |
      | alice@example.com  | editor  |
      | bob@example.com    | author  |
      | carol@example.com  | viewer  |
    Then 3 users should be created
    And they should have the correct roles
```

## Background Usage

```gherkin
Feature: Comment Management

  # Background runs before each scenario
  Background:
    Given I am logged in as "commenter@example.com"
    And there is a published article "Test Article"
    And I am viewing the article

  Scenario: Add comment
    When I enter comment "Great article!"
    And I click "Post Comment"
    Then I should see my comment
    And the comment count should be 1

  Scenario: Edit comment
    Given I have commented "My thoughts"
    When I click edit on my comment
    And I change it to "My updated thoughts"
    And I save
    Then I should see "My updated thoughts"
```

## Using Tags

```gherkin
@smoke @critical
Feature: User Login
  Critical authentication functionality

  @positive
  Scenario: Valid login
    # Happy path test

  @negative
  Scenario: Invalid login
    # Error case test

  @slow @external-service
  Scenario: Two-factor authentication
    # Test requiring SMS service
```

Run with: `pytest -m smoke` or `pytest -m "login and not slow"`
