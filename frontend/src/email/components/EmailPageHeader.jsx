import EmailNav from "./EmailNav.jsx";
export default function EmailPageHeader({ title, description, actions }) {
  return <><header className="email-page-header"><div><span className="email-eyebrow">Email</span><h1>{title}</h1><p>{description}</p></div>{actions && <div className="email-header-actions">{actions}</div>}</header><EmailNav /></>;
}
