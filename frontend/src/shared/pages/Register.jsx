import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { register } from "../services/authService.js";

/**
 * Register Page
 *
 * Public account creation route for starting a new CRM session.
 */

function Register() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  function updateField(event) {
    setFormData((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      await register(formData);
      navigate("/dashboard", { replace: true });
    } catch (requestError) {
      const data = requestError.response?.data;
      setError(data?.email?.[0] || data?.password?.[0] || "Unable to register.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>Register</h1>

        <label>
          Email
          <input
            autoComplete="email"
            name="email"
            onChange={updateField}
            required
            type="email"
            value={formData.email}
          />
        </label>

        <label>
          Password
          <input
            autoComplete="new-password"
            minLength="8"
            name="password"
            onChange={updateField}
            required
            type="password"
            value={formData.password}
          />
        </label>

        {error ? <p className="form-error">{error}</p> : null}

        <button className="button button--primary" disabled={isSubmitting} type="submit">
          {isSubmitting ? "Creating account..." : "Register"}
        </button>

        <p className="auth-note">
          Already have an account? <Link to="/login">Login</Link>
        </p>
      </form>
    </section>
  );
}

export default Register;
