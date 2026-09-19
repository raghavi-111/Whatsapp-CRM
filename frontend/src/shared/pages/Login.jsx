import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { login } from "../services/authService.js";

/**
 * Login Page
 *
 * Public authentication route that signs users in and returns them to the
 * originally requested protected route when available.
 */

function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [formData, setFormData] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const nextPath = location.state?.from?.pathname || "/dashboard";

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
      await login(formData);
      navigate(nextPath, { replace: true });
    } catch (requestError) {
      setError(requestError.response?.data?.non_field_errors?.[0] || "Unable to log in.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>Login</h1>

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
            autoComplete="current-password"
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
          {isSubmitting ? "Logging in..." : "Login"}
        </button>

        <p className="auth-note">
          Need an account? <Link to="/register">Register</Link>
        </p>
      </form>
    </section>
  );
}

export default Login;
