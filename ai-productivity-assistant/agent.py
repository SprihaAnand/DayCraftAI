import os
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime

# Load environment variables from .env
load_dotenv()

# Read Gemini API key from environment variable
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("❌ GEMINI_API_KEY not found in your environment variables or .env file.")

# Configure the Gemini API with the key
genai.configure(api_key=api_key)

# Initialize the model
model = genai.GenerativeModel('gemini-1.5-flash')

def generate_schedule(prompt):
    """
    Generate a productivity schedule using Gemini AI
    """
    try:
        system_prompt = f"""
        You are a productivity assistant that creates detailed, actionable schedules.
        
        Current date and time: {datetime.now().strftime("%Y-%m-%d %H:%M")}
        
        Create a detailed daily schedule based on the user's requirements. Include:
        - Specific time blocks
        - Task priorities
        - Break times
        - Realistic time estimates
        - Actionable steps
        
        Format the response as a clear, structured schedule that's easy to follow.
        Use emojis and clear formatting to make it visually appealing.
        
        User Request: {prompt}
        """
        
        response = model.generate_content(system_prompt)
        return response.text
        
    except Exception as e:
        return f"Error generating schedule: {str(e)}"

def analyze_productivity(tasks_completed, time_spent):
    """
    Analyze productivity metrics and provide insights
    """
    try:
        prompt = f"""
        You are a productivity analyst. Analyze the following productivity data and provide insights:
        
        Tasks Completed: {tasks_completed}
        Time Spent: {time_spent}
        
        Provide:
        1. Productivity assessment
        2. Areas for improvement
        3. Specific recommendations
        4. Next steps
        
        Be constructive and actionable in your feedback. Use a friendly, encouraging tone.
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"Error analyzing productivity: {str(e)}"

def suggest_improvements(current_schedule, feedback):
    """
    Suggest improvements to the current schedule based on feedback
    """
    try:
        prompt = f"""
        You are a productivity consultant. Review the current schedule and user feedback to suggest improvements.
        
        Current Schedule:
        {current_schedule}
        
        User Feedback:
        {feedback}
        
        Based on the feedback, suggest specific improvements to the schedule:
        1. Identify problem areas
        2. Propose solutions
        3. Provide an updated schedule
        4. Explain the reasoning behind changes
        
        Make the suggestions practical and implementable. Use clear formatting and emojis.
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"Error suggesting improvements: {str(e)}"

def prioritize_tasks(task_list):
    """
    Prioritize a list of tasks using AI analysis
    """
    try:
        prompt = f"""
        You are a task management expert. Prioritize the following tasks based on importance, urgency, and impact:
        
        Tasks:
        {task_list}
        
        Provide:
        1. Prioritized task list (High, Medium, Low priority levels)
        2. Reasoning for each priority assignment
        3. Suggested time allocation
        4. Dependencies or prerequisites
        
        Use a clear, actionable format with emojis and good structure.
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"Error prioritizing tasks: {str(e)}"

def generate_focus_session(duration, task_type):
    """
    Generate a focused work session plan
    """
    try:
        prompt = f"""
        Create a focused work session plan for {duration} minutes focused on {task_type}.
        
        Include:
        - Warm-up activities (5 minutes)
        - Main work blocks with specific techniques
        - Break intervals (use Pomodoro technique if applicable)
        - Wrap-up activities
        
        Make it practical and motivating. Include productivity tips specific to the task type.
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"Error generating focus session: {str(e)}"

def create_weekly_plan(goals, constraints):
    """
    Create a weekly productivity plan
    """
    try:
        prompt = f"""
        Create a comprehensive weekly productivity plan based on the following:
        
        Goals for the week:
        {goals}
        
        Constraints/Limitations:
        {constraints}
        
        Provide:
        1. Daily themes or focus areas
        2. Goal breakdown across the week
        3. Buffer time for unexpected tasks
        4. Weekly review and planning time
        5. Work-life balance considerations
        
        Make it realistic and achievable.
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"Error creating weekly plan: {str(e)}"